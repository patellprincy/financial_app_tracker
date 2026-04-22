package com.finsightai.presentation.upload

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.vectorResource
import com.finsightai.R
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.finsightai.domain.model.Transaction
import com.finsightai.domain.model.TransactionType
import com.finsightai.ui.components.FinSightBottomNav
import com.finsightai.ui.components.FinSightCard
import com.finsightai.ui.theme.ExpenseRed
import com.finsightai.ui.theme.IncomeGreen
import java.time.format.DateTimeFormatter
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UploadScreen(
    onNavigateToAddExpense: () -> Unit,
    navController: NavController,
    viewModel: UploadViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Upload", style = MaterialTheme.typography.headlineMedium) },
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
                CsvUploadZone(
                    isLoading = uiState.isLoading,
                    onClick = viewModel::onUploadCsvClick
                )
            }

            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .height(1.dp)
                            .background(MaterialTheme.colorScheme.outlineVariant)
                    )
                    Text("or", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .height(1.dp)
                            .background(MaterialTheme.colorScheme.outlineVariant)
                    )
                }
            }

            item {
                OutlinedButton(
                    onClick = onNavigateToAddExpense,
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Icon(ImageVector.vectorResource(R.drawable.add_box), contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text("Add Expense Manually")
                }
            }

            if (uiState.previewTransactions.isNotEmpty()) {
                item {
                    PreviewHeader(
                        count = uiState.previewTransactions.size,
                        onConfirm = viewModel::onConfirmImport
                    )
                }
                items(uiState.previewTransactions) { transaction ->
                    PreviewTransactionItem(transaction = transaction)
                }
            }

            if (uiState.importSuccess) {
                item {
                    ImportSuccessBanner()
                }
            }
        }
    }
}

@Composable
private fun CsvUploadZone(isLoading: Boolean, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .border(
                width = 2.dp,
                color = MaterialTheme.colorScheme.primary.copy(alpha = 0.4f),
                shape = RoundedCornerShape(16.dp)
            )
            .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.04f))
            .clickable { onClick() }
            .padding(32.dp),
        contentAlignment = Alignment.Center
    ) {
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Icon(
                imageVector = ImageVector.vectorResource(R.drawable.cloud_upload),
                contentDescription = null,
                modifier = Modifier.size(48.dp),
                tint = MaterialTheme.colorScheme.primary
            )
            Text(
                text = if (isLoading) "Processing..." else "Upload CSV File",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.primary,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                text = "Supports statements from HDFC, ICICI, SBI, Axis and more",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )
        }
    }
}

@Composable
private fun PreviewHeader(count: Int, onConfirm: () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text(
            text = "$count transactions ready to import",
            style = MaterialTheme.typography.titleMedium,
            color = MaterialTheme.colorScheme.onSurface
        )
        Button(
            onClick = onConfirm,
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp)
        ) {
            Text("Confirm Import")
        }
    }
}

@Composable
private fun PreviewTransactionItem(transaction: Transaction) {
    FinSightCard(
        modifier = Modifier.fillMaxWidth(),
        containerColor = MaterialTheme.colorScheme.surface
    ) {
        Row(
            modifier = Modifier.padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = transaction.category.emoji,
                style = MaterialTheme.typography.titleLarge,
                modifier = Modifier.size(32.dp)
            )
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = transaction.merchant,
                    style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Text(
                    text = transaction.date.format(DateTimeFormatter.ofPattern("MMM d")),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
            Text(
                text = "-₹${String.format(Locale.getDefault(), "%,.0f", transaction.amount)}",
                style = MaterialTheme.typography.titleMedium,
                color = if (transaction.type == TransactionType.INCOME) IncomeGreen else ExpenseRed,
                fontWeight = FontWeight.SemiBold
            )
        }
    }
}

@Composable
private fun ImportSuccessBanner() {
    FinSightCard(containerColor = IncomeGreen.copy(alpha = 0.1f)) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Icon(
                imageVector = ImageVector.vectorResource(R.drawable.check_circle),
                contentDescription = null,
                tint = IncomeGreen,
                modifier = Modifier.size(24.dp)
            )
            Text(
                text = "Transactions imported successfully!",
                style = MaterialTheme.typography.bodyMedium,
                color = IncomeGreen,
                fontWeight = FontWeight.Medium
            )
        }
    }
}
