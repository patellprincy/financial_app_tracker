package com.finsightai.presentation.home

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.finsightai.data.local.SessionManager
import com.finsightai.data.repository.MockDataRepository
import com.finsightai.domain.model.Transaction
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalTime

data class HomeUiState(
    val greeting: String = "",
    val userName: String = "",
    val monthlySpend: Double = 0.0,
    val topCategory: String = "",
    val spendByCategory: Map<String, Double> = emptyMap(),
    val recentTransactions: List<Transaction> = emptyList()
)

class HomeViewModel(application: Application) : AndroidViewModel(application) {

    private val sessionManager = SessionManager(application)

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    init {
        loadMockData()
        observeUserName()
    }

    private fun loadMockData() {
        val spendByCategory = MockDataRepository.getSpendByCategory()
            .mapKeys { it.key.displayName }

        _uiState.update { current ->
            current.copy(
                greeting = buildGreeting(),
                monthlySpend = MockDataRepository.getMonthlySpend(),
                topCategory = MockDataRepository.getTopCategory().displayName,
                spendByCategory = spendByCategory,
                recentTransactions = MockDataRepository.transactions.take(5)
            )
        }
    }

    private fun observeUserName() {
        viewModelScope.launch {
            combine(sessionManager.firstName, sessionManager.lastName) { first, last ->
                when {
                    !first.isNullOrBlank() && !last.isNullOrBlank() -> "$first $last"
                    !first.isNullOrBlank() -> first
                    else -> ""
                }
            }.collect { name ->
                _uiState.update { it.copy(userName = name) }
            }
        }
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
