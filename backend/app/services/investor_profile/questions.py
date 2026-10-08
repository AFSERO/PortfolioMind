"""Data-driven catalog of Investor Profile Assessment questions.

Based directly on `docs/investor_profile_assessment_spec.md`:
- Core questions C01-C12
- Conditional detail cards F01-F04
- Structured sections and option schemas
"""

from typing import Dict, List
from app.schemas.investor_profile import (
    QuestionDefinition,
    QuestionOption,
    SectionDefinition,
)

SECTIONS: List[SectionDefinition] = [
    SectionDefinition(
        id="goals_context",
        title="Goals & Horizon",
        description="Understand what you want this money to achieve and your time horizon.",
        question_ids=["C01", "C02", "C03"],
    ),
    SectionDefinition(
        id="resilience",
        title="Financial Resilience & Capacity",
        description="Evaluate emergency reserves, cash flow stability, and ability to absorb losses.",
        question_ids=["C04", "C05", "C06", "C07"],
    ),
    SectionDefinition(
        id="risk",
        title="Risk Tolerance",
        description="Assess your comfort with market downturns and behavior under stress.",
        question_ids=["C08", "C09"],
    ),
    SectionDefinition(
        id="experience_preferences",
        title="Experience & Approach",
        description="Familiarity with asset classes and how actively you wish to manage decisions.",
        question_ids=["C10", "C11"],
    ),
    SectionDefinition(
        id="policy",
        title="Investment Policy & Restrictions",
        description="Define important exclusions, leverage rules, and personal investment boundaries.",
        question_ids=["C12"],
    ),
]

QUESTIONS: List[QuestionDefinition] = [
    # -------------------------------------------------------------------------
    # C01 — Main Goal
    # -------------------------------------------------------------------------
    QuestionDefinition(
        id="C01",
        section="goals_context",
        layer="core",
        priority="essential",
        text="What is the main job you want this money to do?",
        helper_text="Choose the primary objective that best describes your intent for these investments.",
        question_type="single_choice",
        options=[
            QuestionOption(code="GROW", label="Build long-term wealth", description="Aiming for capital growth over time"),
            QuestionOption(code="PRESERVE", label="Preserve purchasing power", description="Protect savings against inflation with minimal drawdown"),
            QuestionOption(code="RETIREMENT", label="Fund retirement", description="Building or drawing from retirement savings"),
            QuestionOption(code="PURCHASE", label="Pay for a major purchase", description="Buying a home, vehicle, or other defined asset"),
            QuestionOption(code="INCOME", label="Support regular spending", description="Generate consistent dividend or yield payouts"),
            QuestionOption(code="EDUCATION", label="Fund education", description="Tuition, schooling, or family learning costs"),
            QuestionOption(code="LEGACY", label="Leave money to others", description="Intergenerational transfer or charitable legacy"),
            QuestionOption(code="EXPLORING", label="I am still deciding", description="Exploring possibilities without a fixed objective yet"),
        ],
        has_other=True,
        affects_dimensions=["G", "I"],
    ),

    # -------------------------------------------------------------------------
    # C02 — Horizon and Flexibility
    # -------------------------------------------------------------------------
    QuestionDefinition(
        id="C02",
        section="goals_context",
        layer="core",
        priority="essential",
        text="When will you first need money for this goal, and could you delay it?",
        helper_text="Timing and your willingness to delay directly shape appropriate investment risk.",
        question_type="composite",
        options=[
            QuestionOption(code="LT_1Y", label="Under 1 year"),
            QuestionOption(code="Y1_3", label="1 to under 3 years"),
            QuestionOption(code="Y3_5", label="3 to under 5 years"),
            QuestionOption(code="Y5_10", label="5 to under 10 years"),
            QuestionOption(code="GE_10Y", label="10 years or more"),
            QuestionOption(code="ONGOING", label="I need it now and regularly"),
            QuestionOption(code="NO_DATE", label="No planned date"),
        ],
        has_other=True,
        dependencies=["C01"],
        affects_dimensions=["G", "C", "I"],
    ),

    # -------------------------------------------------------------------------
    # C03 — Withdrawals
    # -------------------------------------------------------------------------
    QuestionDefinition(
        id="C03",
        section="goals_context",
        layer="core",
        priority="essential",
        text="Will you need to take money from these investments in the next three years?",
        helper_text="Identifies capital that cannot be treated as fully long-term.",
        question_type="single_choice",
        options=[
            QuestionOption(code="NONE", label="No planned withdrawals", description="All money stays invested for the next 3 years"),
            QuestionOption(code="ONE_OFF", label="One or more one-off withdrawals", description="Specific expected lump sums"),
            QuestionOption(code="REGULAR", label="Regular withdrawals", description="Periodic income or monthly support"),
            QuestionOption(code="BOTH", label="Both one-off and regular withdrawals"),
            QuestionOption(code="POSSIBLE", label="Possibly, but I cannot estimate yet"),
        ],
        has_other=True,
        affects_dimensions=["G", "C", "I"],
    ),

    # -------------------------------------------------------------------------
    # C04 — Accessible Reserves
    # -------------------------------------------------------------------------
    QuestionDefinition(
        id="C04",
        section="resilience",
        layer="core",
        priority="essential",
        text="Outside the money planned for these goals, how long could accessible savings cover essential expenses if your usual income stopped?",
        helper_text="Accessible means cash or equivalents you can use immediately, not locked property or pension funds.",
        question_type="single_choice",
        options=[
            QuestionOption(code="NONE", label="No separate reserve", description="No emergency buffer outside this investment money"),
            QuestionOption(code="LT_1M", label="Under 1 month"),
            QuestionOption(code="M1_3", label="1 to under 3 months"),
            QuestionOption(code="M3_6", label="3 to under 6 months"),
            QuestionOption(code="M6_12", label="6 to under 12 months"),
            QuestionOption(code="GE_12M", label="12 months or more"),
        ],
        has_other=True,
        affects_dimensions=["C", "G"],
    ),

    # -------------------------------------------------------------------------
    # C05 — Cash Flow and Reliability
    # -------------------------------------------------------------------------
    QuestionDefinition(
        id="C05",
        section="resilience",
        layer="core",
        priority="essential",
        text="After essential expenses and required payments, what best describes your usual cash flow and how reliable it is?",
        helper_text="Captures your ability to replenish capital without judging your employment type.",
        question_type="composite",
        options=[
            QuestionOption(code="SURPLUS", label="Usually money left to save"),
            QuestionOption(code="BREAK_EVEN", label="Usually about enough to break even"),
            QuestionOption(code="DEFICIT", label="Often need savings or borrowing"),
            QuestionOption(code="VARIABLE", label="Varies too much to summarize"),
        ],
        has_other=True,
        affects_dimensions=["C", "G"],
    ),

    # -------------------------------------------------------------------------
    # C06 — Obligations
    # -------------------------------------------------------------------------
    QuestionDefinition(
        id="C06",
        section="resilience",
        layer="core",
        priority="recommended",
        text="Could required payments or financial support commitments put pressure on your ability to keep investing?",
        helper_text="Debt service, family support, or fixed obligations.",
        question_type="single_choice",
        options=[
            QuestionOption(code="NONE", label="No material commitments"),
            QuestionOption(code="MANAGEABLE", label="Commitments are comfortably covered"),
            QuestionOption(code="PRESSURE", label="They sometimes strain my finances"),
            QuestionOption(code="ARREARS", label="I am behind or expect difficulty paying"),
            QuestionOption(code="CHANGE_EXPECTED", label="A significant new commitment is expected"),
        ],
        has_other=True,
        affects_dimensions=["C", "G"],
    ),

    # -------------------------------------------------------------------------
    # C07 — Consequences of Loss
    # -------------------------------------------------------------------------
    QuestionDefinition(
        id="C07",
        section="resilience",
        layer="core",
        priority="essential",
        text="If this goal's investment money permanently lost 20% of its value, what would the financial effect be?",
        helper_text="Think about what you could actually afford, separately from how upsetting it would feel.",
        question_type="single_choice",
        options=[
            QuestionOption(code="ESSENTIALS", label="Essential spending or required payments would be at risk"),
            QuestionOption(code="GOAL_UNAFFORDABLE", label="The goal would no longer be affordable"),
            QuestionOption(code="ADJUST_GOAL", label="I could delay or reduce the goal"),
            QuestionOption(code="LITTLE_EFFECT", label="No material change to essentials or this goal"),
        ],
        has_other=True,
        affects_dimensions=["C", "G"],
    ),

    # -------------------------------------------------------------------------
    # C08 — Drawdown Comfort
    # -------------------------------------------------------------------------
    QuestionDefinition(
        id="C08",
        section="risk",
        layer="core",
        priority="essential",
        text="For money you do not need soon, which fall from a previous high could you tolerate without feeling you must change your plan?",
        helper_text="Recovery is uncertain and may take years; some losses may be permanent.",
        question_type="single_choice",
        options=[
            QuestionOption(code="NONE", label="I would not be comfortable with any loss"),
            QuestionOption(code="P5", label="About 5%"),
            QuestionOption(code="P10", label="About 10%"),
            QuestionOption(code="P20", label="About 20%"),
            QuestionOption(code="P30", label="About 30%"),
            QuestionOption(code="P40_PLUS", label="40% or more"),
        ],
        has_other=True,
        affects_dimensions=["T"],
    ),

    # -------------------------------------------------------------------------
    # C09 — Reaction Under Stress
    # -------------------------------------------------------------------------
    QuestionDefinition(
        id="C09",
        section="risk",
        layer="core",
        priority="recommended",
        text="Imagine your long-term investments fall 20% in six months. Your needs are unchanged, but recovery is uncertain. What would you most likely do?",
        helper_text="Provides an additional tolerance signal under hypothetical market stress.",
        question_type="single_choice",
        options=[
            QuestionOption(code="EXIT", label="Sell most or all"),
            QuestionOption(code="REDUCE", label="Reduce risk / sell part"),
            QuestionOption(code="REVIEW", label="Pause and review before deciding"),
            QuestionOption(code="HOLD", label="Keep the plan and hold"),
            QuestionOption(code="ADD_IF_FUNDED", label="Consider adding only if spare money and my plan permit"),
        ],
        has_other=True,
        affects_dimensions=["T"],
    ),

    # -------------------------------------------------------------------------
    # C10 — Product Experience
    # -------------------------------------------------------------------------
    QuestionDefinition(
        id="C10",
        section="experience_preferences",
        layer="core",
        priority="recommended",
        text="Which investments have you used, and how comfortable are you explaining their risks?",
        helper_text="Select product families you have used or understand.",
        question_type="multi_choice",
        options=[
            QuestionOption(code="STOCKS", label="Individual shares"),
            QuestionOption(code="FUNDS", label="Funds / ETFs"),
            QuestionOption(code="BONDS", label="Bonds"),
            QuestionOption(code="METALS", label="Precious metals"),
            QuestionOption(code="FX", label="Foreign currency"),
            QuestionOption(code="CRYPTO", label="Cryptoassets"),
            QuestionOption(code="PROPERTY", label="Property / Real estate"),
            QuestionOption(code="DERIVATIVES", label="Options / Futures"),
            QuestionOption(code="CASH", label="Cash / Term deposits"),
            QuestionOption(code="NONE", label="None yet", exclusive=True),
        ],
        has_other=True,
        affects_dimensions=["P"],
    ),

    # -------------------------------------------------------------------------
    # C11 — Desired Involvement
    # -------------------------------------------------------------------------
    QuestionDefinition(
        id="C11",
        section="experience_preferences",
        layer="core",
        priority="recommended",
        text="How would you like to manage investment decisions?",
        helper_text="Adapts workflow and research burden without equating activity with risk.",
        question_type="single_choice",
        options=[
            QuestionOption(code="LOW_MAINTENANCE", label="Keep a simple plan with occasional reviews"),
            QuestionOption(code="PERIODIC", label="Research and adjust from time to time"),
            QuestionOption(code="ACTIVE", label="Research and make decisions frequently"),
            QuestionOption(code="MIXED", label="A simple core plus some active decisions"),
            QuestionOption(code="LEARNING", label="Help me learn before choosing an approach"),
        ],
        has_other=True,
        affects_dimensions=["P"],
    ),

    # -------------------------------------------------------------------------
    # C12 — Important Restrictions
    # -------------------------------------------------------------------------
    QuestionDefinition(
        id="C12",
        section="policy",
        layer="core",
        priority="recommended",
        text="Are there investments or practices PortfolioMind should avoid when showing ideas?",
        helper_text="Elicits boundaries voluntarily without requiring sensitive identity disclosure.",
        question_type="multi_choice",
        options=[
            QuestionOption(code="NONE", label="No restrictions I want to set now", exclusive=True),
            QuestionOption(code="BORROWING", label="Borrowing to invest"),
            QuestionOption(code="COMPLEX", label="Complex / leveraged products"),
            QuestionOption(code="ILLIQUID", label="Money being locked up / illiquid assets"),
            QuestionOption(code="ASSETS", label="Specific asset classes or products"),
            QuestionOption(code="MARKETS", label="Specific markets or countries"),
            QuestionOption(code="VALUES", label="Activities or products for personal, ethical or religious reasons"),
            QuestionOption(code="ACCESS", label="Investments I cannot access locally"),
        ],
        has_other=True,
        affects_dimensions=["I", "P"],
    ),

    # -------------------------------------------------------------------------
    # F01 — Withdrawal Detail (Conditional on C03)
    # -------------------------------------------------------------------------
    QuestionDefinition(
        id="F01",
        section="goals_context",
        layer="conditional",
        priority="essential",
        text="For this withdrawal, when is it needed and how much of the investment money does it use?",
        helper_text="Specify approximate timing and share or amount.",
        question_type="composite",
        options=[
            QuestionOption(code="NOW", label="Needed now"),
            QuestionOption(code="LT_12M", label="Within 12 months"),
            QuestionOption(code="M12_36", label="12 to 36 months"),
            QuestionOption(code="GE_36M", label="36 months or later"),
        ],
        has_other=True,
        dependencies=["C03"],
        affects_dimensions=["G", "C", "I"],
    ),

    # -------------------------------------------------------------------------
    # F02 — Constraint Detail (Conditional on C12)
    # -------------------------------------------------------------------------
    QuestionDefinition(
        id="F02",
        section="policy",
        layer="conditional",
        priority="recommended",
        text="What exactly should be excluded or limited, and is this a firm rule or a preference?",
        helper_text="Define exact restrictions for your Investment Policy.",
        question_type="composite",
        options=[
            QuestionOption(code="EXCLUDE", label="Exclude it completely (Hard rule)"),
            QuestionOption(code="LIMIT", label="Keep it below a percentage limit"),
            QuestionOption(code="REQUIRE_REVIEW", label="Discuss it with me before suggesting it (Soft preference)"),
        ],
        has_other=True,
        dependencies=["C12"],
        affects_dimensions=["I", "P"],
    ),
]

QUESTIONS_BY_ID: Dict[str, QuestionDefinition] = {q.id: q for q in QUESTIONS}
