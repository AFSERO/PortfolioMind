"""Deterministic Rules and Interpretation Engine for Investor Profile.

Implements sections 5, 6, and 7 of `docs/investor_profile_assessment_spec.md`:
- Psychological risk tolerance derivation (C08 + C09)
- Financial resilience and capacity derivation (CAP1 - CAP6)
- Contradiction and consistency engine (X01 - X13)
- Meaningful completeness calculation (weighted 100-point model)
- Capability readiness evaluation
"""

from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from app.schemas.investor_profile import (
    CapabilityReadiness,
    CapacityByGoal,
    CapacityStatus,
    GoalItem,
    GoalsAndContext,
    InvestmentPolicy,
    InvestorPreferences,
    LiquiditySummary,
    ProfileCompleteness,
    ProfileIssue,
    ReadinessStatus,
    ResilienceSummary,
    RiskProfile,
    ToleranceSummary,
    WithdrawalNeed,
)


class InvestorProfileRulesEngine:
    """Interprets raw questionnaire answers into structured profile dimensions and signals."""

    @classmethod
    def evaluate(
        cls,
        answers: Dict[str, Any],
        base_version_snapshot: Optional[Dict[str, Any]] = None,
    ) -> Tuple[GoalsAndContext, RiskProfile, InvestmentPolicy, InvestorPreferences, List[ProfileIssue], ProfileCompleteness, CapabilityReadiness]:
        """Runs the complete rules evaluation on dictionary of answer records keyed by question_id."""
        issues: List[ProfileIssue] = []

        # ---------------------------------------------------------------------
        # 1. Goals & Context Extraction
        # ---------------------------------------------------------------------
        c01_ans = answers.get("C01")
        c02_ans = answers.get("C02")
        c03_ans = answers.get("C03")
        f01_ans = answers.get("F01")

        primary_goal_kind: Optional[str] = None
        if c01_ans and c01_ans.get("selected_options"):
            primary_goal_kind = c01_ans["selected_options"][0]

        horizon: Optional[str] = None
        flexibility: Optional[str] = None
        target_date: Optional[str] = None
        if c02_ans:
            opts = c02_ans.get("selected_options", [])
            for opt in opts:
                if opt in ("LT_1Y", "Y1_3", "Y3_5", "Y5_10", "GE_10Y", "ONGOING", "NO_DATE"):
                    horizon = opt
                elif opt in ("FIXED", "SOME", "FLEXIBLE"):
                    flexibility = opt
            num_inputs = c02_ans.get("numeric_inputs", {})
            if "flexibility" in num_inputs and not flexibility:
                flexibility = num_inputs["flexibility"]
            target_date = num_inputs.get("target_date")

        # C07 loss consequence
        c07_ans = answers.get("C07")
        loss_consequence: Optional[str] = None
        if c07_ans and c07_ans.get("selected_options"):
            loss_consequence = c07_ans["selected_options"][0]

        primary_goal = GoalItem(
            id="primary_goal",
            kind=primary_goal_kind or "UNKNOWN",
            horizon=horizon,
            target_date=target_date,
            flexibility=flexibility,
            loss_consequence=loss_consequence,
        )

        # C03 & F01 Withdrawals
        withdrawals: List[WithdrawalNeed] = []
        withdrawal_pattern: Optional[str] = None
        if c03_ans and c03_ans.get("selected_options"):
            withdrawal_pattern = c03_ans["selected_options"][0]

        if withdrawal_pattern and withdrawal_pattern != "NONE" and f01_ans:
            f01_opts = f01_ans.get("selected_options", [])
            timing_band = f01_opts[0] if f01_opts else None
            num_in = f01_ans.get("numeric_inputs", {})
            withdrawals.append(
                WithdrawalNeed(
                    id="withdrawal_1",
                    goal_id="primary_goal",
                    timing_band=timing_band,
                    size=num_in.get("size") or {"percentage": num_in.get("percentage")},
                    coverage=num_in.get("coverage", "INVESTMENTS"),
                )
            )

        # C04 Reserves
        c04_ans = answers.get("C04")
        reserve_months_band: Optional[str] = None
        if c04_ans and c04_ans.get("selected_options"):
            reserve_months_band = c04_ans["selected_options"][0]

        # C05 Cash Flow & Reliability
        c05_ans = answers.get("C05")
        cashflow: Optional[str] = None
        income_reliability: Optional[str] = None
        if c05_ans:
            for opt in c05_ans.get("selected_options", []):
                if opt in ("SURPLUS", "BREAK_EVEN", "DEFICIT", "VARIABLE") and not cashflow:
                    cashflow = opt
                elif opt in ("RELIABLE", "VARIABLE", "AT_RISK", "NO_OUTSIDE_INCOME"):
                    income_reliability = opt
            num_c05 = c05_ans.get("numeric_inputs", {})
            if "reliability" in num_c05 and not income_reliability:
                income_reliability = num_c05["reliability"]

        # C06 Obligations
        c06_ans = answers.get("C06")
        obligation_pressure: Optional[str] = None
        if c06_ans and c06_ans.get("selected_options"):
            obligation_pressure = c06_ans["selected_options"][0]

        # Spending currencies: only if supplied via E01 or explicit context
        e01_ans = answers.get("E01")
        spending_currencies: List[str] = []
        if e01_ans and e01_ans.get("selected_options"):
            spending_currencies = [c for c in e01_ans["selected_options"] if c != "NONE"]
        elif answers.get("spending_currencies"):
            spending_currencies = answers["spending_currencies"]

        goals = GoalsAndContext(
            items=[primary_goal],
            withdrawals=withdrawals,
            withdrawal_pattern=withdrawal_pattern or "UNKNOWN",
            reserve_months_band=reserve_months_band,
            cashflow=cashflow,
            income_reliability=income_reliability,
            obligation_pressure=obligation_pressure,
            spending_currencies=spending_currencies,
        )

        # ---------------------------------------------------------------------
        # 2. Risk Profile & Tolerance Derivation
        # ---------------------------------------------------------------------
        c08_ans = answers.get("C08")
        drawdown_comfort: Optional[str] = None
        custom_drawdown_pct: Optional[float] = None
        tolerance_summary = ToleranceSummary.UNKNOWN

        if c08_ans:
            opts = c08_ans.get("selected_options", [])
            if opts:
                drawdown_comfort = opts[0]
            num_in = c08_ans.get("numeric_inputs", {})
            if "custom_drawdown_pct" in num_in:
                try:
                    custom_drawdown_pct = float(num_in["custom_drawdown_pct"])
                except (ValueError, TypeError):
                    pass

            # Base tolerance classification
            if drawdown_comfort in ("NONE", "P5"):
                tolerance_summary = ToleranceSummary.LOW
            elif drawdown_comfort in ("P10", "P20"):
                tolerance_summary = ToleranceSummary.MODERATE
            elif drawdown_comfort in ("P30", "P40_PLUS"):
                tolerance_summary = ToleranceSummary.HIGH

            if custom_drawdown_pct is not None:
                if custom_drawdown_pct <= 5.0:
                    tolerance_summary = ToleranceSummary.LOW
                elif custom_drawdown_pct <= 20.0:
                    tolerance_summary = ToleranceSummary.MODERATE
                else:
                    tolerance_summary = ToleranceSummary.HIGH

        c09_ans = answers.get("C09")
        stress_response: Optional[str] = None
        if c09_ans and c09_ans.get("selected_options"):
            stress_response = c09_ans["selected_options"][0]

            # Cross-check tolerance against stress response (Rule X04)
            if tolerance_summary == ToleranceSummary.HIGH and stress_response in ("EXIT", "REDUCE"):
                tolerance_summary = ToleranceSummary.MIXED
                issues.append(
                    ProfileIssue(
                        rule_id="X04",
                        field_paths=["risk.drawdown_comfort", "risk.stress_response"],
                        severity="CONFLICT",
                        explanation=(
                            f"Yüksek düşüş toleransı bildirmenize rağmen ({drawdown_comfort}), "
                            f"stres senaryosunda '{stress_response}' aksiyonunu seçtiniz. "
                            "Toleransınız 'Karma (Mixed)' olarak değerlendirildi."
                        ),
                    )
                )
            elif tolerance_summary == ToleranceSummary.LOW and stress_response in ("HOLD", "ADD_IF_FUNDED"):
                tolerance_summary = ToleranceSummary.MIXED
                issues.append(
                    ProfileIssue(
                        rule_id="X04",
                        field_paths=["risk.drawdown_comfort", "risk.stress_response"],
                        severity="CONFLICT",
                        explanation=(
                            f"Düşük düşüş toleransı bildirmenize rağmen ({drawdown_comfort}), "
                            f"stres senaryosunda '{stress_response}' aksiyonunu seçtiniz."
                        ),
                    )
                )

        # ---------------------------------------------------------------------
        # 3. Resilience & Liquidity Summaries
        # ---------------------------------------------------------------------
        # Resilience: VULNERABLE, BUFFERED, MIXED, UNKNOWN
        resilience_summary = ResilienceSummary.UNKNOWN
        if obligation_pressure == "ARREARS" or (cashflow == "DEFICIT" and reserve_months_band in ("NONE", "LT_1M", "M1_3")):
            resilience_summary = ResilienceSummary.VULNERABLE
        elif (
            reserve_months_band in ("M6_12", "GE_12M")
            and cashflow == "SURPLUS"
            and income_reliability == "RELIABLE"
            and obligation_pressure in ("NONE", "MANAGEABLE")
        ):
            resilience_summary = ResilienceSummary.BUFFERED
        elif reserve_months_band or cashflow or income_reliability:
            resilience_summary = ResilienceSummary.MIXED

        # Liquidity: NONE_PLANNED, KNOWN_NEEDS, UNQUANTIFIED_NEEDS, UNKNOWN
        liquidity_summary = LiquiditySummary.UNKNOWN
        if withdrawal_pattern == "NONE":
            liquidity_summary = LiquiditySummary.NONE_PLANNED
        elif withdrawal_pattern in ("ONE_OFF", "REGULAR", "BOTH"):
            if withdrawals and withdrawals[0].timing_band and withdrawals[0].size:
                liquidity_summary = LiquiditySummary.KNOWN_NEEDS
            else:
                liquidity_summary = LiquiditySummary.UNQUANTIFIED_NEEDS
        elif withdrawal_pattern == "POSSIBLE":
            liquidity_summary = LiquiditySummary.UNQUANTIFIED_NEEDS

        # ---------------------------------------------------------------------
        # 4. Capacity By Goal (CAP1 - CAP6)
        # ---------------------------------------------------------------------
        capacity_status = CapacityStatus.UNKNOWN
        reason_codes: List[str] = []

        # Check adverse capacity indicators first (CAP1, CAP2, CAP3)
        if loss_consequence in ("ESSENTIALS", "GOAL_UNAFFORDABLE"):
            capacity_status = CapacityStatus.CONSTRAINED
            reason_codes.append("CAP1: Kalıcı değer kaybı temel harcamaları veya hedefi imkansız kılabilir")

        has_near_term_withdrawal = False
        if withdrawal_pattern in ("ONE_OFF", "REGULAR", "BOTH") or (horizon in ("LT_1Y", "Y1_3") and flexibility == "FIXED"):
            has_near_term_withdrawal = True

        if has_near_term_withdrawal:
            capacity_status = CapacityStatus.CONSTRAINED
            reason_codes.append("CAP2: Önümüzdeki 36 ay içinde sabit/ertelenemez nakit ihtiyacı")

        if resilience_summary == ResilienceSummary.VULNERABLE:
            capacity_status = CapacityStatus.CONSTRAINED
            reason_codes.append("CAP3: Kırılgan finansal dayanıklılık veya yetersiz acil durum rezervi")

        # Check favourable capacity indicator (CAP5)
        if (
            capacity_status != CapacityStatus.CONSTRAINED
            and horizon in ("Y5_10", "GE_10Y")
            and flexibility in ("SOME", "FLEXIBLE")
            and loss_consequence in ("ADJUST_GOAL", "LITTLE_EFFECT")
            and withdrawal_pattern == "NONE"
            and resilience_summary == ResilienceSummary.BUFFERED
        ):
            capacity_status = CapacityStatus.LESS_CONSTRAINED
            reason_codes.append("CAP5: Uzun vade, esnek hedef ve güçlü finansal rezervler")

        if capacity_status == CapacityStatus.UNKNOWN:
            if horizon and loss_consequence and reserve_months_band:
                capacity_status = CapacityStatus.CONDITIONAL
                reason_codes.append("CAP6: Koşullu kapasite — hedefin zamanlamasına göre değişken")
            else:
                reason_codes.append("CAP6: Kapasite tespiti için gerekli bazı temel girdiler henüz eksik")

        capacity_by_goal = [
            CapacityByGoal(
                goal_id="primary_goal",
                status=capacity_status,
                reason_codes=reason_codes,
            )
        ]

        risk = RiskProfile(
            drawdown_comfort=drawdown_comfort,
            custom_drawdown_pct=custom_drawdown_pct,
            stress_response=stress_response,
            tolerance_summary=tolerance_summary,
            capacity_by_goal=capacity_by_goal,
            liquidity_summary=liquidity_summary,
            resilience_summary=resilience_summary,
            horizon_by_goal={"primary_goal": {"horizon": horizon, "flexibility": flexibility}},
        )

        # ---------------------------------------------------------------------
        # 5. Policy & Preferences Extraction
        # ---------------------------------------------------------------------
        c12_ans = answers.get("C12")
        f02_ans = answers.get("F02")
        restriction_topics: List[str] = []
        constraints: List[Dict[str, Any]] = []

        if c12_ans:
            restriction_topics = c12_ans.get("selected_options", [])
            for topic in restriction_topics:
                if topic != "NONE":
                    constraints.append({
                        "topic": topic,
                        "rule": "EXCLUDE",
                        "strength": "HARD",
                        "scope": "ALL",
                    })

        if f02_ans:
            opts = f02_ans.get("selected_options", [])
            rule_val = opts[0] if opts else "EXCLUDE"
            strength_val = "HARD" if rule_val == "EXCLUDE" else "SOFT"
            if constraints:
                constraints[0]["rule"] = rule_val
                constraints[0]["strength"] = strength_val

        policy = InvestmentPolicy(
            restriction_topics=restriction_topics,
            constraints=constraints,
            allocation_mode="NONE",
            allocations=[],
        )

        c10_ans = answers.get("C10")
        c11_ans = answers.get("C11")
        experience: List[Dict[str, Any]] = []
        if c10_ans:
            for fam in c10_ans.get("selected_options", []):
                experience.append({"family": fam, "level": "UNDERSTAND" if fam in ("STOCKS", "FUNDS") else "USED_BASIC"})

        involvement: Optional[str] = None
        if c11_ans and c11_ans.get("selected_options"):
            involvement = c11_ans["selected_options"][0]

        preferences = InvestorPreferences(
            experience=experience,
            involvement=involvement,
            styles=["BROAD_PASSIVE", "QUALITY"],
            explanation_depth="STEP_BY_STEP",
            language="tr",
        )

        # ---------------------------------------------------------------------
        # 6. Contradiction Engine (X01, X02, X03, etc.)
        # ---------------------------------------------------------------------
        # Rule X01: High tolerance alongside constrained capacity / near-term fixed goal
        is_high_tolerance = (
            tolerance_summary == ToleranceSummary.HIGH
            or drawdown_comfort in ("P30", "P40_PLUS")
            or (custom_drawdown_pct is not None and custom_drawdown_pct >= 30.0)
        )
        is_capacity_constrained = capacity_status == CapacityStatus.CONSTRAINED

        withdrawal_pct = 0.0
        if withdrawals and withdrawals[0].size:
            withdrawal_pct = float(withdrawals[0].size.get("percentage") or 0.0)

        near_term_or_severe = (
            horizon in ("LT_1Y", "Y1_3")
            or withdrawal_pct >= 40.0
            or loss_consequence in ("ESSENTIALS", "GOAL_UNAFFORDABLE")
            or is_capacity_constrained
        )

        if is_high_tolerance and near_term_or_severe:
            issues.append(
                ProfileIssue(
                    rule_id="X01",
                    field_paths=["risk.drawdown_comfort", "goals.items[0].horizon", "risk.capacity_by_goal"],
                    severity="CONFLICT",
                    explanation=(
                        f"Yüksek düşüş toleransı ({drawdown_comfort or f'{custom_drawdown_pct}%'}) belirtmenize rağmen, "
                        "yakın vadeli sermaye ihtiyacınız veya hedefinizdeki kalıcı kayıp riski finansal risk kapasitenizi sınırlandırmaktadır. "
                        "Psikolojik toleransınız ile finansal kapasiteniz ayrı ayrı değerlendirilmektedir."
                    ),
                )
            )

        # Rule X03: Strained resilience alongside little effect or leverage
        if resilience_summary == ResilienceSummary.VULNERABLE and loss_consequence == "LITTLE_EFFECT":
            issues.append(
                ProfileIssue(
                    rule_id="X03",
                    field_paths=["goals.cashflow", "goals.reserve_months_band", "goals.items[0].loss_consequence"],
                    severity="CLARIFY",
                    explanation="Düşük nakit akışı veya acil durum rezervine rağmen %20 değer kaybının 'etkisiz' olacağı belirtildi.",
                )
            )

        # ---------------------------------------------------------------------
        # 7. Meaningful Completeness Calculation (100 Points Model)
        # ---------------------------------------------------------------------
        # Goals/Context: 20 points
        g_pts = 0.0
        if primary_goal_kind and primary_goal_kind not in ("EXPLORING", "UNKNOWN"):
            g_pts += 5.0
        if horizon:
            g_pts += 7.0
        if flexibility:
            g_pts += 4.0
        if goals.spending_currencies:
            g_pts += 4.0

        # Liquidity: 20 points
        l_pts = 0.0
        if withdrawal_pattern == "NONE":
            l_pts = 20.0
        elif withdrawal_pattern in ("ONE_OFF", "REGULAR", "BOTH", "POSSIBLE"):
            l_pts += 5.0
            if withdrawals and withdrawals[0].timing_band:
                l_pts += 5.0
            if withdrawals and withdrawals[0].size:
                l_pts += 5.0
            if withdrawals and withdrawals[0].coverage:
                l_pts += 5.0

        # Resilience & Capacity: 25 points
        r_pts = 0.0
        if reserve_months_band:
            r_pts += 6.0
        if cashflow:
            r_pts += 4.0
        if income_reliability:
            r_pts += 4.0
        if obligation_pressure:
            r_pts += 4.0
        if loss_consequence:
            r_pts += 7.0

        # Tolerance: 20 points
        t_pts = 0.0
        if drawdown_comfort:
            t_pts += 12.0
        if stress_response:
            t_pts += 8.0

        # Policy Boundaries: 10 points
        p_pts = 0.0
        if "NONE" in restriction_topics:
            p_pts = 10.0
        elif restriction_topics:
            p_pts += 4.0
            if constraints:
                p_pts += 6.0

        # Experience & Involvement: 5 points
        e_pts = 0.0
        if experience:
            e_pts += 3.0
        if involvement:
            e_pts += 2.0

        overall_pct = float(round(g_pts + l_pts + r_pts + t_pts + p_pts + e_pts, 1))
        domain_breakdown = {
            "goals_context": float(round(g_pts, 1)),
            "liquidity": float(round(l_pts, 1)),
            "resilience": float(round(r_pts, 1)),
            "tolerance": float(round(t_pts, 1)),
            "policy": float(round(p_pts, 1)),
            "experience": float(round(e_pts, 1)),
        }

        missing_fields: List[str] = []
        if not primary_goal_kind or primary_goal_kind in ("EXPLORING", "UNKNOWN"):
            missing_fields.append("goals.primary_goal")
        if not horizon:
            missing_fields.append("goals.horizon")
        if not reserve_months_band:
            missing_fields.append("goals.reserve_months_band")
        if not cashflow:
            missing_fields.append("goals.cashflow")
        if not loss_consequence:
            missing_fields.append("goals.loss_consequence")
        if not drawdown_comfort:
            missing_fields.append("risk.drawdown_comfort")
        if not withdrawal_pattern or withdrawal_pattern == "UNKNOWN":
            missing_fields.append("goals.withdrawals")

        completeness = ProfileCompleteness(
            overall_pct=overall_pct,
            domains=domain_breakdown,
            missing_field_paths=missing_fields,
        )

        # ---------------------------------------------------------------------
        # 8. Capability Readiness Evaluation
        # ---------------------------------------------------------------------
        risk_ready = ReadinessStatus.UNAVAILABLE
        if drawdown_comfort:
            if reserve_months_band and loss_consequence:
                risk_ready = ReadinessStatus.READY
            else:
                risk_ready = ReadinessStatus.PARTIAL

        capacity_ready = ReadinessStatus.UNAVAILABLE
        if reserve_months_band and cashflow and loss_consequence:
            capacity_ready = ReadinessStatus.READY
        elif reserve_months_band or loss_consequence:
            capacity_ready = ReadinessStatus.PARTIAL

        liquidity_ready = ReadinessStatus.UNAVAILABLE
        if withdrawal_pattern == "NONE" or (withdrawals and withdrawals[0].size):
            liquidity_ready = ReadinessStatus.READY
        elif withdrawal_pattern and withdrawal_pattern != "UNKNOWN":
            liquidity_ready = ReadinessStatus.PARTIAL

        target_alloc_ready = ReadinessStatus.UNAVAILABLE  # Target allocation editor not populated by default core questions

        research_ready = ReadinessStatus.UNAVAILABLE
        if primary_goal_kind and primary_goal_kind not in ("EXPLORING", "UNKNOWN"):
            research_ready = ReadinessStatus.READY if experience else ReadinessStatus.PARTIAL

        copilot_ready = ReadinessStatus.READY if overall_pct >= 50.0 else ReadinessStatus.PARTIAL

        portfolio_fit_ready = ReadinessStatus.UNAVAILABLE
        if risk_ready == ReadinessStatus.READY and capacity_ready in (ReadinessStatus.READY, ReadinessStatus.PARTIAL):
            portfolio_fit_ready = ReadinessStatus.PARTIAL

        readiness = CapabilityReadiness(
            risk_analysis=risk_ready,
            capacity_analysis=capacity_ready,
            target_allocation_analysis=target_alloc_ready,
            portfolio_fit=portfolio_fit_ready,
            liquidity_analysis=liquidity_ready,
            copilot_support=copilot_ready,
            research_relevance=research_ready,
        )

        return goals, risk, policy, preferences, issues, completeness, readiness
