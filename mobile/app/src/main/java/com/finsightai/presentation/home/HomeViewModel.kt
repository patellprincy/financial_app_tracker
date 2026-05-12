package com.finsightai.presentation.home

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.finsightai.data.local.SessionManager
import com.finsightai.domain.model.CategoryBreakdown
import com.finsightai.domain.model.DashboardSummary
import com.finsightai.domain.model.Transaction
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch
import java.time.LocalTime

data class HomeUiState(
    val isLoading: Boolean = true,
    val error: String? = null,
    val greeting: String = "",
    val userName: String = "",
    val summary: DashboardSummary = DashboardSummary(),
    val categoryBreakdown: List<CategoryBreakdown> = emptyList(),
    val recentTransactions: List<Transaction> = emptyList()
) {
    val isEmpty: Boolean get() = !isLoading && error == null && recentTransactions.isEmpty()
}

class HomeViewModel(application: Application) : AndroidViewModel(application) {

    private val sessionManager = SessionManager(application)

    private val _uiState = MutableStateFlow(HomeUiState())
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    init {
        loadDashboard()
        observeUserName()
    }

    fun loadDashboard() {
        viewModelScope.launch {
            _uiState.update { it.copy(isLoading = true, error = null) }
            // API call will be wired here in the next step
            _uiState.update { it.copy(isLoading = false, greeting = buildGreeting()) }
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
