# Test Scenarios for Interactive Planning

Test these vague prompts to see if the interactive flow improves them:

## Scenario 1: Very Vague Request
**Input:** "party supplies"

**Expected Clarifications:**
- What type of party? (birthday, wedding, graduation)
- How many guests?
- Budget?
- Indoor or outdoor?
- Age group?

**User refinement example:**
- "birthday party for 10-year-old, 15 guests, $100 budget"

**Expected improvement:**
- More specific items (birthday-themed, age-appropriate)
- Right quantities for 15 guests
- Items within budget

---

## Scenario 2: Missing Context
**Input:** "sports equipment"

**Expected Clarifications:**
- Which sport?
- Indoor or outdoor?
- Skill level (beginner, intermediate, advanced)?
- Budget?
- For how many people?

**User refinement example:**
- "cricket for under 16, outdoor in Doha, beginner"

**Expected improvement:**
- Sport-specific items
- Youth sizing
- Heat management items for Doha climate
- Safety gear

---

## Scenario 3: Incomplete Information
**Input:** "hiking gear"

**Expected Clarifications:**
- Duration of hike (day hike vs multi-day)?
- Location/climate?
- Experience level?
- How many people?
- Budget?

**User refinement example:**
- "day hike in mountains, 2 people, moderate difficulty"

**Expected improvement:**
- Appropriate gear for day hike (not overnight camping)
- Safety items (first aid, hydration)
- Weather-appropriate items
- Right quantities for 2 people

---

## Scenario 4: Vague Event
**Input:** "picnic stuff"

**Expected Clarifications:**
- How many people?
- Location (park, beach, backyard)?
- Duration?
- What type of food (bring or buy)?
- Budget?

**User refinement example:**
- "beach picnic, 4 people, 3 hours, hot weather"

**Expected improvement:**
- Beach-specific items (towels, shade)
- Heat management (cooler, ice packs)
- Sun protection
- Right portions for 4 people

---

## Scenario 5: Ambiguous Scope
**Input:** "school supplies"

**Expected Clarifications:**
- Which grade level?
- How many students/children?
- Specific subjects?
- Budget per student?

**User refinement example:**
- "high school, 1 student, math and science focus, $75 budget"

**Expected improvement:**
- Grade-appropriate items
- Subject-specific supplies (graphing calculator, lab notebook)
- Items within budget

---

## What to Test

Run these commands and verify:

```bash
# Test vague prompt
export OPENAI_API_KEY="your-key"
python3 -m shopping_agent.app.main plan "party supplies"

# Expected flow:
# 1. Shows initial plan (generic party items)
# 2. Shows clarifications: "What type of party?", "How many guests?", "Budget?"
# 3. Asks: "Approve this plan?"
# 4. You say: no
# 5. You add: "birthday party for 10-year-old, 15 guests, $100 budget"
# 6. Shows refined plan (specific to birthday, sized for 15 guests, within budget)
# 7. Asks: "Approve this plan?" again
# 8. You say: yes
# 9. ✓ Plan approved!
```

## Success Criteria

After refinement loop, the plan should have:
- ✅ All vague items replaced with specific ones
- ✅ Appropriate quantities based on context
- ✅ Safety/health items relevant to activity
- ✅ Items within budget constraints
- ✅ Context-appropriate choices (climate, duration, age)
- ✅ No more critical clarifications needed
