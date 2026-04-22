package com.finsightai.presentation.home

import androidx.lifecycle.ViewModel
import com.finsightai.data.repository.MockDataRepository
import com.finsightai.domain.model.Transaction
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import java.time.LocalTime

data class HomeUiState(
    val greeting: String = "",
    val userName: String = "Rahul",
    val monthlySpend: Double = 0.0,
    val topCategory: String = "",
    val spendByCategory: Map<String, Double> = emptyMap(),
    val recentTransactions: List<Transaction> = emptyList()
)

class HomeViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    private fun loadData() {
        val spendByCategory = MockDataRepository.getSpendByCategory()
            .mapKeys { it.key.displayName }

        _uiState.value = HomeUiState(
            greeting = buildGreeting(),
            userName = "Rahul",
            monthlySpend = MockDataRepository.getMonthlySpend(),
            topCategory = MockDataRepository.getTopCategory().displayName,
            spendByCategory = spendByCategory,
            recentTransactions = MockDataRepository.transactions.take(5)
        )
    }

    private fun buildGreeting(): String {
        return when (LocalTime.now().hour) {
            in 5..11 -> "Good morning,"
            in 12..16 -> "Good afternoon,"
            in 17..20 -> "Good evening,"
            else -> "Good night,"
        }
    }
}
