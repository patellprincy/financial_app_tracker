package com.finsightai.presentation.insights

import androidx.lifecycle.ViewModel
import com.finsightai.data.repository.MockDataRepository
import com.finsightai.domain.model.InsightItem
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

data class InsightsUiState(
    val insights: List<InsightItem> = emptyList()
)

class InsightsViewModel : ViewModel() {

    private val _uiState = MutableStateFlow(InsightsUiState())
    val uiState: StateFlow<InsightsUiState> = _uiState.asStateFlow()

    init {
        _uiState.value = InsightsUiState(insights = MockDataRepository.insights)
    }
}
