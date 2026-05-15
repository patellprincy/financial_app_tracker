package com.finsightai.data.repository

import com.finsightai.domain.model.ChatMessage
import com.finsightai.domain.model.InsightItem
import com.finsightai.domain.model.InsightType
import com.finsightai.domain.model.MessageSender
import java.time.LocalDateTime

object MockDataRepository {

    val insights: List<InsightItem> = listOf(
        InsightItem(
            id = "1",
            title = "Food spending is up 23%",
            description = "You spent $1,590 on food this week compared to $1,290 last week. Dining out is the main driver.",
            type = InsightType.PATTERN,
            value = "+23%"
        ),
        InsightItem(
            id = "2",
            title = "Unusual large purchase",
            description = "Your $5,200 travel transaction is significantly higher than your average travel spend of $1,200.",
            type = InsightType.UNUSUAL,
            value = "$5,200"
        ),
        InsightItem(
            id = "3",
            title = "You can save $4,000 this month",
            description = "By reducing food delivery by 3 orders a week, you could save around $4,000 by month end.",
            type = InsightType.SUGGESTION,
            value = "$4,000"
        ),
        InsightItem(
            id = "4",
            title = "Transport costs are stable",
            description = "Your transport spending has been consistent at around $500 per week for the past month.",
            type = InsightType.PATTERN,
            value = "Stable"
        ),
        InsightItem(
            id = "5",
            title = "Subscription overlap detected",
            description = "You may be paying for multiple streaming services. Consider if you need all of them.",
            type = InsightType.SUGGESTION,
            value = "$948/mo"
        ),
        InsightItem(
            id = "6",
            title = "Shopping spike on weekends",
            description = "80% of your shopping transactions happen on Saturday and Sunday.",
            type = InsightType.PATTERN,
            value = "Weekends"
        )
    )

    val suggestedChatPrompts = listOf(
        "How much did I spend this month?",
        "What's my biggest expense category?",
        "Show me unusual transactions",
        "How can I save more money?",
        "Compare this month vs last month"
    )

    val mockAiReplies = mapOf(
        "how much did i spend this month?" to "You've spent $14,971 so far this month. That's about 18% of your monthly income. Food and Shopping are your top two categories.",
        "what's my biggest expense category?" to "Your biggest category is Shopping at $4,298 (29%), followed by Food & Dining at $1,590 (11%). Would you like tips to reduce either?",
        "show me unusual transactions" to "I found 2 unusual transactions: $5,200 on travel (4x your usual travel spend), and $2,499 at a shopping retailer (2x your usual shopping amount).",
        "how can i save more money?" to "Based on your spending patterns, here are 3 actionable tips:\n\n1. Cut food delivery by 3 orders/week → Save $4,000\n2. Consolidate streaming to one service → Save $649/mo\n3. Set a $3,000 weekly shopping limit → Save $2,000+",
        "compare this month vs last month" to "This month vs last month:\n\n• Total: $14,971 vs $13,200 (+13%)\n• Food: $1,590 vs $1,290 (+23%)\n• Transport: $495 vs $510 (-3%)\n• Shopping: $4,298 vs $3,100 (+39%)\n\nOverall spending is up. Shopping is the main driver."
    )

    fun getInitialChatMessages(): List<ChatMessage> = listOf(
        ChatMessage(
            id = "welcome",
            content = "Hi! I'm your FinSight AI assistant. I can answer questions about your spending, find patterns, and help you save more. What would you like to know?",
            sender = MessageSender.AI,
            timestamp = LocalDateTime.now().minusMinutes(1)
        )
    )
}
