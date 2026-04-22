package com.finsightai.data.repository

import com.finsightai.domain.model.ChatMessage
import com.finsightai.domain.model.InsightItem
import com.finsightai.domain.model.InsightType
import com.finsightai.domain.model.MessageSender
import com.finsightai.domain.model.Transaction
import com.finsightai.domain.model.TransactionCategory
import com.finsightai.domain.model.TransactionType
import java.time.LocalDate
import java.time.LocalDateTime

object MockDataRepository {

    val transactions: List<Transaction> = listOf(
        Transaction("1", "Swiggy", TransactionCategory.FOOD, 450.0, LocalDate.now().minusDays(1)),
        Transaction("2", "Uber", TransactionCategory.TRANSPORT, 180.0, LocalDate.now().minusDays(1)),
        Transaction("3", "Amazon", TransactionCategory.SHOPPING, 2499.0, LocalDate.now().minusDays(2)),
        Transaction("4", "Netflix", TransactionCategory.ENTERTAINMENT, 649.0, LocalDate.now().minusDays(3)),
        Transaction("5", "BigBasket", TransactionCategory.GROCERIES, 1200.0, LocalDate.now().minusDays(3)),
        Transaction("6", "Apollo Pharmacy", TransactionCategory.HEALTH, 350.0, LocalDate.now().minusDays(4)),
        Transaction("7", "Zomato", TransactionCategory.FOOD, 320.0, LocalDate.now().minusDays(4)),
        Transaction("8", "Ola", TransactionCategory.TRANSPORT, 220.0, LocalDate.now().minusDays(5)),
        Transaction("9", "Myntra", TransactionCategory.SHOPPING, 1799.0, LocalDate.now().minusDays(5)),
        Transaction("10", "Salary", TransactionCategory.INCOME, 85000.0, LocalDate.now().minusDays(6), type = TransactionType.INCOME),
        Transaction("11", "Electricity Bill", TransactionCategory.UTILITIES, 1450.0, LocalDate.now().minusDays(7)),
        Transaction("12", "Starbucks", TransactionCategory.FOOD, 540.0, LocalDate.now().minusDays(7)),
        Transaction("13", "Rapido", TransactionCategory.TRANSPORT, 95.0, LocalDate.now().minusDays(8)),
        Transaction("14", "Hotstar", TransactionCategory.ENTERTAINMENT, 299.0, LocalDate.now().minusDays(9)),
        Transaction("15", "Udemy", TransactionCategory.EDUCATION, 499.0, LocalDate.now().minusDays(10)),
        Transaction("16", "IndiGo", TransactionCategory.TRAVEL, 5200.0, LocalDate.now().minusDays(12)),
        Transaction("17", "D-Mart", TransactionCategory.GROCERIES, 980.0, LocalDate.now().minusDays(13)),
        Transaction("18", "HDFC Credit Card", TransactionCategory.UTILITIES, 3200.0, LocalDate.now().minusDays(14)),
        Transaction("19", "Freelance", TransactionCategory.INCOME, 15000.0, LocalDate.now().minusDays(15), type = TransactionType.INCOME),
        Transaction("20", "McDonald's", TransactionCategory.FOOD, 280.0, LocalDate.now().minusDays(15))
    )

    val insights: List<InsightItem> = listOf(
        InsightItem(
            id = "1",
            title = "Food spending is up 23%",
            description = "You spent ₹1,590 on food this week compared to ₹1,290 last week. Dining out is the main driver.",
            type = InsightType.PATTERN,
            value = "+23%"
        ),
        InsightItem(
            id = "2",
            title = "Unusual large purchase",
            description = "Your ₹5,200 IndiGo transaction is significantly higher than your average travel spend of ₹1,200.",
            type = InsightType.UNUSUAL,
            value = "₹5,200"
        ),
        InsightItem(
            id = "3",
            title = "You can save ₹4,000 this month",
            description = "By reducing food delivery by 3 orders a week, you could save around ₹4,000 by month end.",
            type = InsightType.SUGGESTION,
            value = "₹4,000"
        ),
        InsightItem(
            id = "4",
            title = "Transport costs are stable",
            description = "Your transport spending has been consistent at around ₹500 per week for the past month.",
            type = InsightType.PATTERN,
            value = "Stable"
        ),
        InsightItem(
            id = "5",
            title = "Subscription overlap detected",
            description = "You're paying for both Netflix and Hotstar. Consider if you need both streaming services.",
            type = InsightType.SUGGESTION,
            value = "₹948/mo"
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
        "how much did i spend this month?" to "You've spent ₹14,971 so far this month. That's about 18% of your monthly income. Food and Shopping are your top two categories.",
        "what's my biggest expense category?" to "Your biggest category is Shopping at ₹4,298 (29%), followed by Food & Dining at ₹1,590 (11%). Would you like tips to reduce either?",
        "show me unusual transactions" to "I found 2 unusual transactions: ₹5,200 to IndiGo on April 9 (4x your usual travel spend), and ₹2,499 to Amazon on April 19 (2x your usual shopping amount).",
        "how can i save more money?" to "Based on your spending patterns, here are 3 actionable tips:\n\n1. Cut food delivery by 3 orders/week → Save ₹4,000\n2. Consolidate streaming to one service → Save ₹649/mo\n3. Set a ₹3,000 weekly shopping limit → Save ₹2,000+",
        "compare this month vs last month" to "This month vs last month:\n\n• Total: ₹14,971 vs ₹13,200 (+13%)\n• Food: ₹1,590 vs ₹1,290 (+23%)\n• Transport: ₹495 vs ₹510 (-3%)\n• Shopping: ₹4,298 vs ₹3,100 (+39%)\n\nOverall spending is up. Shopping is the main driver."
    )

    fun getTransactionById(id: String): Transaction? = transactions.find { it.id == id }

    fun getMonthlySpend(): Double = transactions
        .filter { it.type == TransactionType.EXPENSE }
        .sumOf { it.amount }

    fun getTopCategory(): TransactionCategory {
        return transactions
            .filter { it.type == TransactionType.EXPENSE }
            .groupBy { it.category }
            .maxByOrNull { it.value.sumOf { t -> t.amount } }
            ?.key ?: TransactionCategory.OTHER
    }

    fun getSpendByCategory(): Map<TransactionCategory, Double> {
        return transactions
            .filter { it.type == TransactionType.EXPENSE }
            .groupBy { it.category }
            .mapValues { entry -> entry.value.sumOf { it.amount } }
            .toList()
            .sortedByDescending { it.second }
            .toMap()
    }

    fun getInitialChatMessages(): List<ChatMessage> = listOf(
        ChatMessage(
            id = "welcome",
            content = "Hi! I'm your FinSight AI assistant. I can answer questions about your spending, find patterns, and help you save more. What would you like to know?",
            sender = MessageSender.AI,
            timestamp = LocalDateTime.now().minusMinutes(1)
        )
    )
}
