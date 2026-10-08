"""Intent detection and semantics engine for PortfolioMind Copilot.

Determines intent type, user authority execution mode, extracts entities,
identifies missing parameters, and defines required context groups.
"""

from datetime import date, timedelta
import re
from typing import Any, List, Optional

from app.schemas.copilot import (
    AcquisitionType,
    ContextGroup,
    ExecutionMode,
    IntentResult,
    IntentType,
)
from app.services.copilot.holding_resolver import (
    COMMODITY_ALIASES,
    normalize_text,
    parse_acquisition_type,
    parse_currency_amount,
    parse_quantity,
)


class IntentClassifier:
    """Classifies user messages into structured intent results with authority semantics."""

    @classmethod
    def classify(
        cls,
        message: str,
        current_page_context: Optional[dict[str, Any]] = None,
        recent_messages: Optional[List[Any]] = None,
    ) -> IntentResult:
        """Deterministic pre-routing and semantics engine."""
        text = message.strip()
        lower = text.lower()
        norm = normalize_text(text)

        # ---------------------------------------------------------------------
        # 0. Multi-Turn Follow-Up Resolution against Previous Action Draft
        # ---------------------------------------------------------------------
        last_assistant_meta: Optional[dict[str, Any]] = None
        if recent_messages:
            for m in reversed(recent_messages):
                role = getattr(m, "role", None) or (m.get("role") if isinstance(m, dict) else None)
                if role == "assistant":
                    meta = getattr(m, "structured_metadata", None) or (
                        m.get("structured_metadata") if isinstance(m, dict) else None
                    )
                    if meta:
                        last_assistant_meta = meta
                        break

        prev_draft = (last_assistant_meta.get("action_draft") or {}) if last_assistant_meta else {}
        prev_missing = (last_assistant_meta.get("missing_fields") or []) if last_assistant_meta else []
        prev_intent = last_assistant_meta.get("intent") if last_assistant_meta else None

        # Check if user message answers a previous incomplete portfolio import
        prev_batch = last_assistant_meta.get("import_batch") if last_assistant_meta else None
        prev_batch_has_pending = False
        if prev_batch:
            status_val = prev_batch.get("status")
            if status_val in ("DRAFT", "NEEDS_INPUT") or prev_batch.get("needs_review_count", 0) > 0:
                prev_batch_has_pending = True

        is_explicit_new_import = bool(
            re.search(
                r"\b(my current portfolio|add my current portfolio|add my portfolio|current portfolio|i already own|portf[oö]y[uü]m[a-z]*|mevcut portföyüm|mevcut varlıklarım|bunlar benim portföyüm|elimde olanlar|i have:)\b",
                lower,
            )
        )
        if prev_batch_has_pending and not is_explicit_new_import:
            qty_match = re.search(r"(?:adet|quantity|miktar|is|için|icin)?\s*[:=]?\s*(\d+(?:[.,]\d+)?)", text, re.IGNORECASE)
            if qty_match:
                return IntentResult(
                    intent=IntentType.PORTFOLIO_IMPORT_UPDATE,
                    confidence=0.95,
                    entities={"message": text},
                    requires_context=[ContextGroup.PORTFOLIO_HOLDINGS.value],
                    execution_mode=ExecutionMode.PROPOSE,
                    missing_information=[],
                    reason="User supplied missing quantity/resolution for pending portfolio import draft.",
                )

        # Check if the user is answering a previous incomplete transaction draft
        user_is_new_command = bool(
            re.search(r"\b(bought|buy|aldım|aldık|sold|sell|sattım|sattık|hediye|gift|gave me|transfer)\b", lower)
        )
        if (
            not user_is_new_command
            and prev_intent == IntentType.TRANSACTION_ENTRY.value
            and prev_missing
            and not prev_draft.get("is_complete")
        ):
            # Check if user message supplies missing information
            date_resolved: Optional[str] = None
            if re.search(r"\b(today|bugün)\b", norm):
                date_resolved = str(date.today())
            elif re.search(r"\b(yesterday|dün)\b", norm):
                date_resolved = str(date.today() - timedelta(days=1))
            else:
                date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
                if date_match:
                    date_resolved = date_match.group(1)

            use_curr_price = bool(
                re.search(r"\b(current value|current price|güncel değer|güncel fiyat|piyasa fiyatı|current)\b", norm)
            )

            # Check for symbol in response (e.g. "Yarım Altın / Gold Half HALF" or "HALF")
            resolved_sym: Optional[str] = None
            for alias_k, sym_v in COMMODITY_ALIASES.items():
                if re.search(r"\b" + re.escape(alias_k) + r"\b", norm):
                    resolved_sym = sym_v
                    break
            if not resolved_sym:
                words = re.findall(r"\b[A-Za-z0-9\.\-_]{2,10}\b", text)
                for w in words:
                    if w.isupper() and w not in {"HALF", "GOLD", "TODAY", "BUGÜN", "USD", "EUR", "TRY"}:
                        resolved_sym = w
                        break

            parsed_price, parsed_cur = parse_currency_amount(text)
            parsed_qty = parse_quantity(text)

            # Merge with previous draft
            merged_entities = dict(prev_draft.get("entities") or {})
            for k in [
                "action",
                "acquisition_type",
                "symbol",
                "instrument_name",
                "quantity",
                "unit_price",
                "currency",
                "affects_cash",
                "cash_outflow",
                "transaction_date",
            ]:
                if k in prev_draft and prev_draft[k] is not None:
                    merged_entities[k] = prev_draft[k]

            if date_resolved:
                merged_entities["transaction_date"] = date_resolved
            if use_curr_price:
                merged_entities["use_current_price"] = True
            if resolved_sym:
                merged_entities["symbol"] = resolved_sym
            if parsed_qty is not None:
                merged_entities["quantity"] = float(parsed_qty)
            if parsed_price is not None:
                merged_entities["price"] = float(parsed_price)
                if parsed_cur:
                    merged_entities["currency"] = parsed_cur

            # Recalculate missing information
            rem_missing: list[str] = []
            if not merged_entities.get("symbol"):
                rem_missing.append("symbol")
            if merged_entities.get("quantity") is None:
                rem_missing.append("quantity")

            acq_type = merged_entities.get("acquisition_type", AcquisitionType.PURCHASE.value)
            if (
                acq_type not in (AcquisitionType.GIFT_IN.value, AcquisitionType.TRANSFER_IN.value)
                and not merged_entities.get("use_current_price")
                and merged_entities.get("price") is None
            ):
                rem_missing.append("price")

            if not merged_entities.get("transaction_date"):
                rem_missing.append("transaction_date")

            if not rem_missing:
                return IntentResult(
                    intent=IntentType.TRANSACTION_ENTRY,
                    confidence=0.98,
                    entities=merged_entities,
                    requires_context=[
                        ContextGroup.EXISTING_HOLDING.value,
                        ContextGroup.PRICE_CONTEXT.value,
                        ContextGroup.INSTRUMENT.value,
                    ],
                    execution_mode=ExecutionMode.AUTO_APPLY,
                    missing_information=[],
                    reason="Follow-up response successfully completed all required transaction details.",
                )
            elif len(rem_missing) < len(prev_missing):
                # Progress was made, still need some info
                return IntentResult(
                    intent=IntentType.TRANSACTION_ENTRY,
                    confidence=0.94,
                    entities=merged_entities,
                    requires_context=[
                        ContextGroup.EXISTING_HOLDING.value,
                        ContextGroup.PRICE_CONTEXT.value,
                        ContextGroup.INSTRUMENT.value,
                    ],
                    execution_mode=ExecutionMode.NEEDS_INPUT,
                    missing_information=rem_missing,
                    reason=f"Partial follow-up. Still requires: {', '.join(rem_missing)}.",
                )

        # ---------------------------------------------------------------------
        # 1. PORTFOLIO_IMPORT (Multi-holding portfolio import detection)
        # ---------------------------------------------------------------------
        import_keyword_match = bool(
            re.search(
                r"\b(my current portfolio|add my current portfolio|add my portfolio|current portfolio|i already own|portf[oö]y[uü]m[a-z]*|mevcut portföyüm|mevcut varlıklarım|bunlar benim portföyüm|elimde olanlar|i have:)\b",
                lower,
            )
        )
        from app.services.copilot.import_parsers.natural_language import NaturalLanguagePortfolioParser
        parsed_holdings = NaturalLanguagePortfolioParser.parse(text)
        distinct_symbols = {it.symbol for it in parsed_holdings if it.symbol}

        gift_match = re.search(r"\b(gift|hediye|gave me|verdi|bağış|hibe|hediye etti)\b", lower)
        transfer_match = re.search(r"\b(transfer|aktarım|aktar|aktarıldı|virman)\b", lower)
        is_single_gift_or_transfer = bool(gift_match or transfer_match)

        if not is_single_gift_or_transfer and (len(distinct_symbols) >= 2 or (import_keyword_match and len(parsed_holdings) >= 1)):
            return IntentResult(
                intent=IntentType.PORTFOLIO_IMPORT,
                confidence=0.96,
                entities={"holdings_count": len(parsed_holdings), "source_type": "NATURAL_LANGUAGE"},
                requires_context=[
                    ContextGroup.PORTFOLIO_HOLDINGS.value,
                    ContextGroup.INSTRUMENT.value,
                ],
                execution_mode=ExecutionMode.PROPOSE,
                missing_information=[],
                reason=f"Detected multi-holding portfolio import request with {len(parsed_holdings)} assets.",
            )

        # ---------------------------------------------------------------------
        # 2. TRANSACTION_ENTRY / PORTFOLIO_CHANGE Detection
        # ---------------------------------------------------------------------
        bought_match = re.search(r"\b(bought|buy|aldım|aldık|satın aldım)\b", lower)
        sold_match = re.search(r"\b(sold|sell|sattım|sattık)\b", lower)
        gift_match = re.search(r"\b(gift|hediye|gave me|verdi|bağış|hibe|hediye etti)\b", lower)
        transfer_match = re.search(r"\b(transfer|aktarım|aktar|aktarıldı|virman)\b", lower)
        add_match = re.search(
            r"\b(add|ekle|ekler misin|ekleyebilir misin|put|put next to|yanına ekle|kaydet|yaz)\b",
            lower,
        )

        # Check if query references any commodity alias
        matched_alias_symbol: Optional[str] = None
        for alias_k, sym_v in sorted(COMMODITY_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True):
            if re.search(r"\b" + re.escape(alias_k) + r"\b", norm):
                matched_alias_symbol = sym_v
                break

        is_journal_cmd = bool(re.search(r"\b(add note|take a note|journal note|journal entry|not ekle|not al|not düş)\b", lower))
        is_watchlist_cmd = bool(re.search(r"\b(watchlist|takip listesi|takip listeme|takip listemden|izleme listesi)\b", lower))

        is_tx_intent = (
            not is_journal_cmd
            and not is_watchlist_cmd
            and (
                bought_match
                or sold_match
                or gift_match
                or transfer_match
                or (add_match and (matched_alias_symbol or "portfolio" in lower or "holding" in lower or "varlık" in lower))
            )
        )

        if is_tx_intent:
            acq_type, affects_cash, cash_outflow = parse_acquisition_type(text)
            if gift_match:
                action = "RECEIVE_ASSET"
                acq_type = AcquisitionType.GIFT_IN
                affects_cash = False
                cash_outflow_val = 0.0
            elif transfer_match:
                action = "RECEIVE_ASSET"
                acq_type = AcquisitionType.TRANSFER_IN
                affects_cash = False
                cash_outflow_val = 0.0
            elif sold_match:
                action = "SELL"
                acq_type = AcquisitionType.SALE
                affects_cash = True
                cash_outflow_val = 0.0
            else:
                action = "BUY"
                acq_type = AcquisitionType.PURCHASE
                affects_cash = True
                cash_outflow_val = 0.0

            # Symbol resolution
            symbol: Optional[str] = matched_alias_symbol
            if not symbol:
                # Look for uppercase ticker symbol
                sym_match = re.search(
                    r"\b(?:bought|buy|aldım|sold|sell|sattım|add|ekle)\s+(?:(\d+(?:\.\d+)?)\s+)?([A-Za-z0-9\.\-_]{2,10})\b",
                    text,
                    re.IGNORECASE,
                )
                if sym_match:
                    candidate = sym_match.group(2).strip()
                    if candidate.upper() not in {"SOME", "MORE", "A", "THE", "AN", "BUGÜN", "TODAY", "IT"}:
                        symbol = candidate.upper()

            # Fallback symbol from page context
            if not symbol and current_page_context and current_page_context.get("symbol"):
                symbol = str(current_page_context["symbol"]).upper()

            # Quantity extraction
            parsed_qty = parse_quantity(text)
            quantity: Optional[float] = float(parsed_qty) if parsed_qty is not None else None

            # Price & Currency extraction
            parsed_price, parsed_cur = parse_currency_amount(text)
            price: Optional[float] = float(parsed_price) if parsed_price is not None else None
            currency: str = parsed_cur or "USD"

            # Date extraction
            tx_date: Optional[str] = None
            if re.search(r"\b(today|bugün)\b", norm):
                tx_date = str(date.today())
            elif re.search(r"\b(yesterday|dün)\b", norm):
                tx_date = str(date.today() - timedelta(days=1))
            else:
                date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
                if date_match:
                    tx_date = date_match.group(1)

            entities: dict[str, Any] = {
                "action": action,
                "acquisition_type": acq_type.value,
                "affects_cash": affects_cash,
                "cash_outflow": cash_outflow_val,
            }
            if symbol:
                entities["symbol"] = symbol
            if quantity is not None:
                entities["quantity"] = quantity
            if price is not None:
                entities["price"] = price
                entities["currency"] = currency
            if tx_date:
                entities["transaction_date"] = tx_date

            # Missing information check
            missing_info: list[str] = []
            if not symbol:
                missing_info.append("symbol")
            if quantity is None:
                missing_info.append("quantity")

            # For GIFT_IN and TRANSFER_IN, cash price is never required!
            if acq_type not in (AcquisitionType.GIFT_IN, AcquisitionType.TRANSFER_IN):
                if price is None:
                    missing_info.append("price")

            if not tx_date:
                missing_info.append("transaction_date")

            requires_ctx = [
                ContextGroup.EXISTING_HOLDING.value,
                ContextGroup.PRICE_CONTEXT.value,
                ContextGroup.INSTRUMENT.value,
            ]

            if missing_info:
                return IntentResult(
                    intent=IntentType.TRANSACTION_ENTRY,
                    confidence=0.92,
                    entities=entities,
                    requires_context=requires_ctx,
                    execution_mode=ExecutionMode.NEEDS_INPUT,
                    missing_information=missing_info,
                    reason=f"Transaction/acquisition requires missing information: {', '.join(missing_info)}.",
                )
            else:
                return IntentResult(
                    intent=IntentType.TRANSACTION_ENTRY,
                    confidence=0.96,
                    entities=entities,
                    requires_context=requires_ctx,
                    execution_mode=ExecutionMode.AUTO_APPLY,
                    missing_information=[],
                    reason="All critical transaction/acquisition details are present.",
                )

        # ---------------------------------------------------------------------
        # 1.9. FINANCIAL_DISCOVERY (Adaptive Financial Discovery)
        # ---------------------------------------------------------------------
        risk_discovery_match = bool(
            re.search(
                r"\b(how much risk|what risk|risk can i take|risk should i take|don't know how much risk|dont know how much risk|not sure how much risk|risk capacity|ne kadar risk|risk almalıyım|risk alabileceğimi bilmiyorum|risk kapasitem)\b",
                lower,
            )
        )
        invest_discovery_match = bool(
            re.search(
                r"\b(how much i can invest|how much can i invest|how much should i invest|how much to invest|how much can i save|don't know how much i can invest|dont know how much i can invest|invest every month|invest each month|ne kadar yatırım|aylık ne kadar yatırım|ayda ne kadar yatırım|ne kadar yatırım yapabilirim|ne kadar birikim yapabilirim|ne kadar tasarruf edebilirim)\b",
                lower,
            )
        )
        emergency_discovery_match = bool(
            re.search(
                r"\b(emergency fund is enough|emergency fund enough|is my emergency fund|emergency reserve is enough|emergency reserve enough|emergency buffer enough|not sure whether my emergency fund|not sure if my emergency fund|how much emergency fund|acil durum fonum yeterli mi|acil durum fonu yeterli mi|yedek akçem yeterli mi|acil durum param yeterli mi|acil durum rezervim yeterli mi)\b",
                lower,
            )
        )
        if risk_discovery_match or invest_discovery_match or emergency_discovery_match:
            topic = (
                "risk_capacity"
                if risk_discovery_match
                else ("monthly_investment_capacity" if invest_discovery_match else "emergency_fund_adequacy")
            )
            return IntentResult(
                intent=IntentType.FINANCIAL_DISCOVERY,
                confidence=0.96,
                entities={"discovery_topic": topic},
                requires_context=[
                    ContextGroup.FINANCIAL_CONTEXT.value,
                    ContextGroup.FINANCIAL_INTELLIGENCE.value,
                    ContextGroup.FINANCIAL_GOALS.value,
                    ContextGroup.MANDATES.value,
                    ContextGroup.USER_PROFILE.value,
                    ContextGroup.INVESTMENT_POLICY.value,
                    ContextGroup.PORTFOLIO_SUMMARY.value,
                ],
                execution_mode=ExecutionMode.READ_ONLY,
                missing_information=[],
                reason=f"Adaptive financial discovery inquiry regarding {topic}.",
            )

        # ---------------------------------------------------------------------
        # 2. POLICY_CHANGE (Explicit mutation of targets/allocations/rules/profile)
        # ---------------------------------------------------------------------
        # E.g. "My income is stable now and I can take more risk.", "Change my crypto target allocation to 15%."
        risk_profile_match = re.search(
            r"\b(income is stable|take more risk|more risk|risk alabilirim|daha fazla risk|gelirim stabil|gelirim d[uü]zenli)\b",
            lower,
        )
        if risk_profile_match:
            return IntentResult(
                intent=IntentType.POLICY_CHANGE,
                confidence=0.95,
                entities={
                    "policy_field": "risk_tolerance",
                    "change_kind": "RISK_AND_INCOME",
                    "new_income_reliability": "RELIABLE",
                    "new_drawdown_comfort": "P30",
                    "description": "Gelir güvenirliği 'Düzenli' ve düşüş toleransı '%30' olarak güncellenecek.",
                },
                requires_context=[ContextGroup.USER_PROFILE.value, ContextGroup.INVESTMENT_POLICY.value],
                execution_mode=ExecutionMode.PROPOSE,
                missing_information=[],
                reason="User stated income is stable and desires increased risk tolerance.",
            )

        policy_change_match = re.search(
            r"\b(change|set|update|ayarla|değiştir|yap)\b.*\b(target|allocation|hedep|hedef|pay|oran)\b",
            lower,
        )

        if policy_change_match:
            # Check for asset category (crypto, stock, gold, etc.)
            cat_match = re.search(r"\b(crypto|kripto|stock|hisse|gold|altın|cash|nakit|bist|fon|fund)\b", lower)
            category = cat_match.group(1).lower() if cat_match else "general"

            # Check percentage
            pct_matches = re.findall(r"(\d+(?:\.\d+)?)\s*%", text)
            new_value: Optional[float] = None
            old_value: Optional[float] = None
            if pct_matches:
                if len(pct_matches) >= 2:
                    old_value = float(pct_matches[0]) / 100.0
                    new_value = float(pct_matches[1]) / 100.0
                else:
                    new_value = float(pct_matches[0]) / 100.0

            entities = {
                "policy_field": f"{category}_target_allocation",
                "category": category,
            }
            if new_value is not None:
                entities["new_value"] = new_value
            if old_value is not None:
                entities["old_value"] = old_value

            if new_value is None:
                return IntentResult(
                    intent=IntentType.POLICY_CHANGE,
                    confidence=0.9,
                    entities=entities,
                    requires_context=[ContextGroup.INVESTMENT_POLICY.value, ContextGroup.PORTFOLIO_SUMMARY.value],
                    execution_mode=ExecutionMode.NEEDS_INPUT,
                    missing_information=["new_target_value"],
                    reason="Target policy adjustment missing target percentage.",
                )

            return IntentResult(
                intent=IntentType.POLICY_CHANGE,
                confidence=0.95,
                entities=entities,
                requires_context=[ContextGroup.INVESTMENT_POLICY.value, ContextGroup.PORTFOLIO_SUMMARY.value],
                execution_mode=ExecutionMode.AUTO_APPLY,
                missing_information=[],
                reason="Explicit user command to modify investment policy target.",
            )

        # ---------------------------------------------------------------------
        # 2b. WATCHLIST_UPDATE (Add/remove candidate from watchlist)
        # ---------------------------------------------------------------------
        watchlist_term = re.search(r"\b(watchlist|takip listesi|takip listeme|takip listemden|izleme listesi)\b", lower)
        is_add = bool(re.search(r"\b(add|put|watch|ekle|ekler misin|ekleyebilir misin)\b", lower))
        is_remove = bool(re.search(r"\b(remove|delete|çıkar|sil|kaldır)\b", lower))
        if watchlist_term and (is_add or is_remove):
            words = re.findall(r"\b[A-Za-z0-9\.\-_]{2,10}\b", text)
            sym = None
            for w in words:
                if w.isupper() and w not in {"ADD", "REMOVE", "FROM", "TO", "MY", "WATCHLIST", "BUY", "SELL", "THE"}:
                    sym = w
                    break
            if not sym:
                sym_match = re.search(r"\b(?:add|remove|ekle|çıkar)\s+([A-Za-z0-9\.\-_]{2,10})\b", text, re.IGNORECASE)
                if sym_match and sym_match.group(1).upper() not in {"TO", "FROM", "MY", "A", "THE", "WATCHLIST"}:
                    sym = sym_match.group(1).upper()

            action = "REMOVE_WATCHLIST" if is_remove else "ADD_WATCHLIST"
            entities = {"action": action, "symbol": sym}
            if not sym:
                return IntentResult(
                    intent=IntentType.WATCHLIST_UPDATE,
                    confidence=0.9,
                    entities=entities,
                    requires_context=[ContextGroup.WATCHLIST.value],
                    execution_mode=ExecutionMode.NEEDS_INPUT,
                    missing_information=["symbol"],
                    reason=f"Watchlist {action} requires an asset or symbol.",
                )
            return IntentResult(
                intent=IntentType.WATCHLIST_UPDATE,
                confidence=0.95,
                entities=entities,
                requires_context=[ContextGroup.WATCHLIST.value, ContextGroup.INSTRUMENT.value],
                execution_mode=ExecutionMode.AUTO_APPLY,
                missing_information=[],
                reason=f"Explicit user request to {action} symbol {sym}.",
            )

        # ---------------------------------------------------------------------
        # 2c. JOURNAL_ENTRY (Create decision log / journal note)
        # ---------------------------------------------------------------------
        journal_match = re.search(r"\b(add note|take a note|journal note|journal entry|not ekle|not al|not düş)\b", lower)
        if journal_match:
            note_content = text[journal_match.end():].strip().lstrip(":").strip()
            if not note_content and ":" in text:
                note_content = text.split(":", 1)[1].strip()

            if not note_content:
                return IntentResult(
                    intent=IntentType.JOURNAL_ENTRY,
                    confidence=0.9,
                    entities={"action": "CREATE_JOURNAL_ENTRY"},
                    requires_context=[ContextGroup.DECISION_HISTORY.value],
                    execution_mode=ExecutionMode.NEEDS_INPUT,
                    missing_information=["note_content"],
                    reason="Journal entry requires note content.",
                )

            title = note_content[:50] + ("..." if len(note_content) > 50 else "")
            return IntentResult(
                intent=IntentType.JOURNAL_ENTRY,
                confidence=0.95,
                entities={
                    "action": "CREATE_JOURNAL_ENTRY",
                    "title": title,
                    "summary": note_content,
                },
                requires_context=[ContextGroup.DECISION_HISTORY.value],
                execution_mode=ExecutionMode.AUTO_APPLY,
                missing_information=[],
                reason="Explicit user request to record a journal note.",
            )

        # ---------------------------------------------------------------------
        # 2.5. FINANCIAL_ANALYSIS ("Analyze my finances / overall financial situation")
        # ---------------------------------------------------------------------
        fin_analysis_match = bool(
            re.search(
                r"\b(analyze my finances|analyze my financial situation|analyze my entire financial situation|financial situation|financial health|finansal durum|finansal sağlığ|bütün finansal durum|tüm finansal durum|finansal durumumu analiz et)\b",
                lower,
            )
        )
        if fin_analysis_match:
            return IntentResult(
                intent=IntentType.FINANCIAL_ANALYSIS,
                confidence=0.98,
                entities={"topic": "financial_situation"},
                requires_context=[
                    ContextGroup.FINANCIAL_CONTEXT.value,
                    ContextGroup.FINANCIAL_GOALS.value,
                    ContextGroup.MANDATES.value,
                    ContextGroup.FINANCIAL_INTELLIGENCE.value,
                    ContextGroup.PORTFOLIO_SUMMARY.value,
                    ContextGroup.USER_PROFILE.value,
                ],
                execution_mode=ExecutionMode.READ_ONLY,
                missing_information=[],
                reason="Comprehensive financial situation analysis request.",
            )

        # ---------------------------------------------------------------------
        # 2.6. CONVERSATIONAL FINANCIAL UPDATES (Phase 4.1)
        # ---------------------------------------------------------------------
        # Income / Expenses update
        income_match = re.search(
            r"\b(earn|now earn|salary|income|gelir|aylık gelirim|aylık net gelirim|kazanıyorum)\b.*?(?:[:=]|\bis\b|\bnow\b|\bartık\b)?\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:k\b|bin\b)?\s*(try|tl|usd|eur)?",
            lower,
        )
        expense_match = re.search(
            r"\b(essential expenses|spending|harcamam|zorunlu harcamam|giderim)\b.*?(?:[:=]|\bis\b)?\s*([0-9]+(?:[.,][0-9]+)?)\s*(?:k\b|bin\b)?\s*(try|tl|usd|eur)?",
            lower,
        )
        if (
            (income_match or expense_match)
            and any(w in lower for w in ["job", "earn", "salary", "income", "gelir", "expense", "harcama", "gider", "now earn", "oldu"])
            and not any(w in lower for w in ["bought", "buy", "sold", "sell", "aldım", "sattım"])
        ):
            monthly_income = None
            if income_match:
                try:
                    val = float(income_match.group(2).replace(",", "."))
                    if "k" in lower or "bin" in lower:
                        val *= 1000
                    monthly_income = val
                except ValueError:
                    pass

            monthly_expenses = None
            if expense_match:
                try:
                    val = float(expense_match.group(2).replace(",", "."))
                    if "k" in lower or "bin" in lower:
                        val *= 1000
                    monthly_expenses = val
                except ValueError:
                    pass

            currency = "TRY"
            if "usd" in lower or "$" in lower:
                currency = "USD"
            elif "eur" in lower or "€" in lower:
                currency = "EUR"

            return IntentResult(
                intent=IntentType.UPDATE_FINANCIAL_CONTEXT,
                confidence=0.95,
                entities={
                    "monthly_net_income": monthly_income,
                    "monthly_essential_expenses": monthly_expenses,
                    "planning_currency": currency,
                    "user_request": text,
                },
                requires_context=[ContextGroup.FINANCIAL_CONTEXT.value],
                execution_mode=ExecutionMode.PROPOSE,
                missing_information=[],
                reason="User conversational update to income or essential expenses.",
            )

        # Goal creation
        goal_create_match = re.search(
            r"\b(want to buy a house|buy a house|buy a home|home purchase|retirement goal|ev alma hedefi|emeklilik hedefi|create a goal|yeni hedef)\b",
            lower,
        )
        if goal_create_match:
            g_type = "OTHER"
            name = "New Goal"
            if any(w in lower for w in ["house", "home", "ev"]):
                g_type = "HOME_PURCHASE"
                name = "Home Purchase"
            elif any(w in lower for w in ["retire", "emekli"]):
                g_type = "RETIREMENT"
                name = "Retirement"

            amt_match = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:k\b|bin\b|m\b|milyon\b)?\s*(try|tl|usd|eur)?", lower)
            amt = None
            if amt_match:
                try:
                    amt = float(amt_match.group(1).replace(",", "."))
                    if "m" in lower or "milyon" in lower:
                        amt *= 1000000
                    elif "k" in lower or "bin" in lower:
                        amt *= 1000
                except ValueError:
                    pass

            return IntentResult(
                intent=IntentType.CREATE_GOAL,
                confidence=0.95,
                entities={
                    "name": name,
                    "goal_type": g_type,
                    "target_amount": amt,
                    "target_currency": "TRY",
                    "user_request": text,
                },
                requires_context=[ContextGroup.FINANCIAL_GOALS.value],
                execution_mode=ExecutionMode.PROPOSE,
                missing_information=[],
                reason="User conversational creation of a financial goal.",
            )

        # Virtual capital transfer between mandates
        transfer_cap_match = bool(
            re.search(
                r"\b(move|transfer|aktar|aktarımı|transfer capital)\b.*\b(mandate|mandatine|fund|fonuna|reserve|growth|retirement|home)\b",
                lower,
            )
        )
        if transfer_cap_match:
            return IntentResult(
                intent=IntentType.TRANSFER_CAPITAL,
                confidence=0.95,
                entities={"user_request": text},
                requires_context=[ContextGroup.MANDATES.value],
                execution_mode=ExecutionMode.PROPOSE,
                missing_information=[],
                reason="User request for virtual capital transfer between mandates.",
            )

        # ---------------------------------------------------------------------
        # 3. POLICY_DISCUSSION (Discussion/analysis of policy, hypothetical)
        # ---------------------------------------------------------------------
        # E.g. "Would increasing crypto to 15% make sense?", "Kriptoyu %15'e çıkarmak mantıklı mı?"
        policy_disc_match = re.search(
            r"\b(would|should|could|what if|mantıklı mı|uygun mu|nasıl olur|düşünsem|faydalı mı)\b.*\b(target|allocation|crypto|kripto|exposure|artırsam|çıkarsam)\b",
            lower,
        ) or re.search(r"\b(thinking about|artırmayı düşünüyorum|artırsam)\b", lower)
        if policy_disc_match:
            cat_match = re.search(r"\b(crypto|kripto|stock|hisse|gold|altın|cash|nakit|fon|fund)\b", lower)
            category = cat_match.group(1).lower() if cat_match else "portfolio"
            return IntentResult(
                intent=IntentType.POLICY_DISCUSSION,
                confidence=0.9,
                entities={"topic": category},
                requires_context=[
                    ContextGroup.INVESTMENT_POLICY.value,
                    ContextGroup.PORTFOLIO_SUMMARY.value,
                    ContextGroup.PORTFOLIO_HOLDINGS.value,
                ],
                execution_mode=ExecutionMode.READ_ONLY,
                missing_information=[],
                reason="Hypothetical analysis / policy discussion without mutation authorization.",
            )

        # ---------------------------------------------------------------------
        # 4. RESEARCH_REQUEST (Ask to research / deep dive an asset)
        # ---------------------------------------------------------------------
        # E.g. "Research THF again.", "THF için derin araştırma yap", "Analyse AAPL fundamentals"
        research_match = re.search(
            r"\b(research|deep research|araştır|incele|yeniden araştır)\s+([A-Za-z0-9\.\-_]{2,10})\b",
            text,
            re.IGNORECASE,
        ) or re.search(
            r"\b([A-Za-z0-9\.\-_]{2,10})\s+(hakkında|için)?\s*(araştırma|deep research|analiz)\b",
            text,
            re.IGNORECASE,
        )
        if research_match:
            sym = (
                research_match.group(2)
                if research_match.lastindex and research_match.lastindex >= 2 and research_match.group(2)
                else research_match.group(1)
            ).upper()
            return IntentResult(
                intent=IntentType.RESEARCH_REQUEST,
                confidence=0.95,
                entities={"symbol": sym},
                requires_context=[
                    ContextGroup.INSTRUMENT.value,
                    ContextGroup.INTELLIGENCE_STATE.value,
                    ContextGroup.RESEARCH_HISTORY.value,
                    ContextGroup.WATCHLIST.value,
                ],
                execution_mode=ExecutionMode.PROPOSE,
                missing_information=[],
                reason="Explicit user request to trigger research workflow on a symbol.",
            )

        # ---------------------------------------------------------------------
        # 5. ASSET_ANALYSIS (Questions regarding specific asset thesis/state)
        # ---------------------------------------------------------------------
        # E.g. "What was my original thesis for UBER?", "Why is UBER on my watchlist?", "UBER analizi"
        # Check if symbol appears in message
        words = re.findall(r"\b[A-Za-z0-9\.\-_]{2,10}\b", text)
        known_keywords = {
            "WHAT", "WHY", "HOW", "WHEN", "WHERE", "MY", "IS", "ON", "FOR",
            "THE", "WAS", "ARE", "IN", "TO", "OF", "AND", "PORTFOLIO", "RISK",
            "RISKS", "BIGGEST", "LARGEST", "HOLDINGS", "POSITIONS", "THESIS",
            "WATCHLIST", "TARGET", "ALLOCATION", "CURRENT", "BUY", "SELL"
        }
        potential_symbols = [
            w.upper() for w in words
            if w.isupper() and len(w) >= 2 and w.upper() not in known_keywords
        ]
        # Also check page_context
        ctx_symbol = current_page_context.get("symbol") if current_page_context else None
        target_symbol = potential_symbols[0] if potential_symbols else (ctx_symbol.upper() if ctx_symbol else None)

        if target_symbol and any(
            k in lower for k in ["thesis", "tez", "neden", "why", "watchlist", "takip", "review", "durumu", "analiz"]
        ):
            return IntentResult(
                intent=IntentType.ASSET_ANALYSIS,
                confidence=0.92,
                entities={"symbol": target_symbol},
                requires_context=[
                    ContextGroup.INSTRUMENT.value,
                    ContextGroup.ASSET.value,
                    ContextGroup.INTELLIGENCE_STATE.value,
                    ContextGroup.RESEARCH_HISTORY.value,
                    ContextGroup.WATCHLIST.value,
                    ContextGroup.DISCOVERY_PROVENANCE.value,
                    ContextGroup.DECISION_HISTORY.value,
                ],
                execution_mode=ExecutionMode.READ_ONLY,
                missing_information=[],
                reason=f"Specific inquiry on asset/instrument thesis or status for {target_symbol}.",
            )

        # ---------------------------------------------------------------------
        # 6. PORTFOLIO_ANALYSIS (Risk, allocation, performance, positions)
        # ---------------------------------------------------------------------
        # E.g. "What are the biggest risks in my portfolio?", "What are the largest positions in my current portfolio?"
        portfolio_match = any(
            term in lower
            for term in [
                "portfolio", "portföy", "holdings", "positions", "varlıklarım",
                "risk", "risks", "allocation", "dağılım", "performans", "performance",
                "net worth", "net değer", "kazanç", "kayıp", "largest", "biggest", "en büyük"
            ]
        )
        if portfolio_match:
            return IntentResult(
                intent=IntentType.PORTFOLIO_ANALYSIS,
                confidence=0.94,
                entities={},
                requires_context=[
                    ContextGroup.USER_PROFILE.value,
                    ContextGroup.PORTFOLIO_SUMMARY.value,
                    ContextGroup.PORTFOLIO_HOLDINGS.value,
                    ContextGroup.INTELLIGENCE_STATE.value,
                    ContextGroup.INVESTMENT_POLICY.value,
                ],

                execution_mode=ExecutionMode.READ_ONLY,
                missing_information=[],
                reason="Portfolio-level risk, holdings, or allocation inquiry.",
            )

        # ---------------------------------------------------------------------
        # 7. GENERAL_QUESTION / UNKNOWN fallback
        # ---------------------------------------------------------------------
        return IntentResult(
            intent=IntentType.GENERAL_QUESTION,
            confidence=0.8,
            entities={},
            requires_context=[ContextGroup.USER_PROFILE.value, ContextGroup.RECENT_CONVERSATION.value],
            execution_mode=ExecutionMode.READ_ONLY,
            missing_information=[],
            reason="General inquiry or educational question.",
        )
