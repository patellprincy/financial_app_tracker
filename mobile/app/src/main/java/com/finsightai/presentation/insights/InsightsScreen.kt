package com.finsightai.presentation.insights

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.vectorResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.finsightai.R
import com.finsightai.domain.model.InsightItem
import com.finsightai.domain.model.InsightType
import com.finsightai.ui.components.FinSightBottomNav
import com.finsightai.ui.components.FinSightCard
import com.finsightai.ui.theme.ExpenseRed
import com.finsightai.ui.theme.IncomeGreen

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun InsightsScreen(
    navController: NavController,
    viewModel: InsightsViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Insights", style = MaterialTheme.typography.headlineMedium) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        },
        bottomBar = { FinSightBottomNav(navController) },
        containerColor = MaterialTheme.colorScheme.background
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            item {
                InsightsSummaryCard(
                    totalInsights = uiState.insights.size,
                    unusualCount = uiState.insights.count { it.type == InsightType.UNUSUAL },
                    suggestionsCount = uiState.insights.count { it.type == InsightType.SUGGESTION }
                )
            }
            items(uiState.insights) { insight ->
                InsightCard(insight = insight)
            }
        }
    }
}

@Composable
private fun InsightsSummaryCard(totalInsights: Int, unusualCount: Int, suggestionsCount: Int) {
    FinSightCard(
        modifier = Modifier.fillMaxWidth(),
        containerColor = MaterialTheme.colorScheme.primaryContainer
    ) {
        Row(
            modifier = Modifier.padding(20.dp),
            horizontalArrangement = Arrangement.SpaceEvenly
        ) {
            SummaryStatItem(label = "Insights", value = "$totalInsights", color = MaterialTheme.colorScheme.primary)
            SummaryStatItem(label = "Unusual", value = "$unusualCount", color = ExpenseRed)
            SummaryStatItem(label = "Tips", value = "$suggestionsCount", color = IncomeGreen)
        }
    }
}

@Composable
private fun SummaryStatItem(label: String, value: String, color: Color) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = value,
            style = MaterialTheme.typography.headlineLarge,
            color = color,
            fontWeight = FontWeight.Bold
        )
        Text(
            text = label,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
    }
}

@Composable
private fun InsightCard(insight: InsightItem) {
    val (icon, color, label) = when (insight.type) {
        InsightType.PATTERN -> Triple(ImageVector.vectorResource(R.drawable.auto_graph), MaterialTheme.colorScheme.primary, "Pattern")
        InsightType.UNUSUAL -> Triple(ImageVector.vectorResource(R.drawable.warning), ExpenseRed, "Unusual")
        InsightType.SUGGESTION -> Triple(ImageVector.vectorResource(R.drawable.lightbulb), IncomeGreen, "Tip")
    }

    FinSightCard(
        modifier = Modifier.fillMaxWidth(),
        containerColor = MaterialTheme.colorScheme.surface
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Box(
                    modifier = Modifier
                        .size(40.dp)
                        .background(color = color.copy(alpha = 0.12f), shape = CircleShape),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = icon,
                        contentDescription = null,
                        tint = color,
                        modifier = Modifier.size(20.dp)
                    )
                }
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = label,
                        style = MaterialTheme.typography.labelSmall,
                        color = color,
                        fontWeight = FontWeight.SemiBold
                    )
                    Text(
                        text = insight.title,
                        style = MaterialTheme.typography.titleMedium,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
                if (insight.value.isNotEmpty()) {
                    Text(
                        text = insight.value,
                        style = MaterialTheme.typography.titleMedium,
                        color = color,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
            Spacer(modifier = Modifier.height(10.dp))
            Text(
                text = insight.description,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant
            )
        }
    }
}
