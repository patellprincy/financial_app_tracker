package com.finsightai.presentation.upload

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarDuration
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.SnackbarResult
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.vectorResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavController
import com.finsightai.R
import com.finsightai.domain.model.ExtractedTransaction
import com.finsightai.domain.model.SelectedFile
import com.finsightai.domain.model.StatementUploadResponse
import com.finsightai.ui.components.FinSightBottomNav
import com.finsightai.ui.components.FinSightCard
import com.finsightai.ui.theme.ExpenseRed
import com.finsightai.ui.theme.IncomeGreen
import com.finsightai.ui.theme.NeutralAmber
import java.util.Locale

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun UploadScreen(
    onNavigateToAddExpense: () -> Unit,
    onNavigateHome: () -> Unit,
    navController: NavController,
    viewModel: UploadViewModel = viewModel()
) {
    val uiState by viewModel.uiState.collectAsStateWithLifecycle()
    val snackbarHostState = remember { SnackbarHostState() }

    // Undo snackbar — fires on each unique undoEvent.id
    LaunchedEffect(uiState.undoEvent?.id) {
        uiState.undoEvent?.let {
            val result = snackbarHostState.showSnackbar(
                message = "Transaction removed",
                actionLabel = "Undo",
                duration = SnackbarDuration.Short
            )
            if (result == SnackbarResult.ActionPerformed) {
                viewModel.undoRemoveTransaction()
            }
            viewModel.clearUndoEvent()
        }
    }

    val pdfPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenDocument()
    ) { uri ->
        if (uri != null) viewModel.onFileSelected(uri)
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Upload Statement", style = MaterialTheme.typography.headlineMedium) },
                colors = TopAppBarDefaults.topAppBarColors(
                    containerColor = MaterialTheme.colorScheme.background
                )
            )
        },
        bottomBar = { FinSightBottomNav(navController) },
        snackbarHost = { SnackbarHost(snackbarHostState) },
        containerColor = MaterialTheme.colorScheme.background
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            when (val state = uiState.uploadState) {

                // ── Idle: file selection ───────────────────────────────────
                is UploadState.Idle -> {
                    item {
                        PdfPickerZone(
                            selectedFile = uiState.selectedFile,
                            onClick = { pdfPickerLauncher.launch(arrayOf("application/pdf")) }
                        )
                    }
                    item { OrDivider() }
                    item {
                        OutlinedButton(
                            onClick = onNavigateToAddExpense,
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp)
                        ) {
                            Icon(ImageVector.vectorResource(R.drawable.add_box), null)
                            Spacer(Modifier.width(8.dp))
                            Text("Add Expense Manually")
                        }
                    }
                    if (uiState.selectedFile != null) {
                        item {
                            UploadActionButton(
                                label = "Upload & Parse PDF",
                                onClick = viewModel::onUpload
                            )
                        }
                    }
                }

                // ── Uploading ──────────────────────────────────────────────
                is UploadState.Uploading -> {
                    item { UploadingIndicator(fileName = uiState.selectedFile?.name) }
                }

                // ── Success: preview + manage ──────────────────────────────
                is UploadState.Success -> {
                    item {
                        ParseResultBanner(
                            response = state.response,
                            visibleCount = uiState.visibleTransactions.size
                        )
                    }

                    // Parse warning (no transactions found)
                    if (state.response.parseError != null && uiState.visibleTransactions.isEmpty()
                        && uiState.removedTransactions.isEmpty()
                    ) {
                        item { ParseErrorCard(message = state.response.parseError) }
                    }

                    // Summary totals
                    if (uiState.visibleTransactions.isNotEmpty()) {
                        item {
                            PreviewSummaryRow(
                                totalExpense = uiState.totalExpense,
                                totalIncome = uiState.totalIncome
                            )
                        }
                    }

                    // Preview header
                    if (uiState.visibleTransactions.isNotEmpty() || uiState.removedTransactions.isNotEmpty()) {
                        item {
                            PreviewHeader(
                                visibleCount = uiState.visibleTransactions.size,
                                removedCount = uiState.removedTransactions.size,
                                onRestoreAll = viewModel::resetPreview
                            )
                        }
                    }

                    // Empty state
                    if (uiState.visibleTransactions.isEmpty() && uiState.removedTransactions.isNotEmpty()) {
                        item { EmptyPreviewState(onRestoreAll = viewModel::resetPreview) }
                    }

                    if (uiState.importSuccess) {
                        // ── Import complete ────────────────────────────────
                        item {
                            ImportSuccessCard(
                                importedCount = uiState.importedCount,
                                failedCount = uiState.failedCount
                            )
                        }
                        item {
                            Button(
                                onClick = onNavigateHome,
                                modifier = Modifier.fillMaxWidth().height(52.dp),
                                shape = RoundedCornerShape(12.dp)
                            ) {
                                Icon(ImageVector.vectorResource(R.drawable.home), null, Modifier.size(18.dp))
                                Spacer(Modifier.width(8.dp))
                                Text("Go to Dashboard", style = MaterialTheme.typography.labelLarge)
                            }
                        }
                        item {
                            OutlinedButton(
                                onClick = viewModel::onReset,
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(12.dp)
                            ) {
                                Icon(ImageVector.vectorResource(R.drawable.cloud_upload), null)
                                Spacer(Modifier.width(8.dp))
                                Text("Upload Another File")
                            }
                        }
                    } else {
                        // Transaction rows with remove button
                        itemsIndexed(
                            items = uiState.visibleTransactions,
                            key = { _, txn -> txn.rawText.hashCode() }
                        ) { _, txn ->
                            ExtractedTransactionRow(
                                transaction = txn,
                                onRemove = { viewModel.removeTransaction(txn) }
                            )
                        }

                        // Import action (button + loading + error)
                        item {
                            ImportSection(
                                count = uiState.visibleTransactions.size,
                                isImporting = uiState.isImporting,
                                importError = uiState.importError,
                                onImport = viewModel::importSelectedTransactions
                            )
                        }

                        item {
                            OutlinedButton(
                                onClick = viewModel::onReset,
                                enabled = !uiState.isImporting,
                                modifier = Modifier.fillMaxWidth(),
                                shape = RoundedCornerShape(12.dp)
                            ) {
                                Icon(ImageVector.vectorResource(R.drawable.cloud_upload), null)
                                Spacer(Modifier.width(8.dp))
                                Text("Upload Another File")
                            }
                        }
                    }
                }

                // ── Error ──────────────────────────────────────────────────
                is UploadState.Error -> {
                    item {
                        UploadErrorCard(
                            message = state.message,
                            fileName = uiState.selectedFile?.name,
                            onRetry = viewModel::onUpload,
                            onReset = viewModel::onReset
                        )
                    }
                }
            }
        }
    }
}

// ── File picker zone ───────────────────────────────────────────────────────

@Composable
private fun PdfPickerZone(selectedFile: SelectedFile?, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .border(2.dp, MaterialTheme.colorScheme.primary.copy(alpha = 0.4f), RoundedCornerShape(16.dp))
            .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.04f))
            .clickable { onClick() }
            .padding(28.dp),
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
            if (selectedFile == null) {
                Text("Select PDF Statement", style = MaterialTheme.typography.titleMedium,
                    color = MaterialTheme.colorScheme.primary, fontWeight = FontWeight.SemiBold)
                Text("Tap to choose a bank statement PDF", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
            } else {
                Text(selectedFile.name, style = MaterialTheme.typography.titleSmall,
                    color = MaterialTheme.colorScheme.onSurface, fontWeight = FontWeight.SemiBold,
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
                selectedFile.size?.let {
                    Text(formatFileSize(it), style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Text("Tap to choose a different file", style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.7f))
            }
        }
    }
}

// ── Upload button ──────────────────────────────────────────────────────────

@Composable
private fun UploadActionButton(label: String, onClick: () -> Unit) {
    Button(
        onClick = onClick,
        modifier = Modifier.fillMaxWidth().height(52.dp),
        shape = RoundedCornerShape(12.dp)
    ) {
        Icon(ImageVector.vectorResource(R.drawable.cloud_upload), null, Modifier.size(18.dp))
        Spacer(Modifier.width(8.dp))
        Text(label, style = MaterialTheme.typography.labelLarge)
    }
}

// ── Uploading indicator ────────────────────────────────────────────────────

@Composable
private fun UploadingIndicator(fileName: String?) {
    FinSightCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            CircularProgressIndicator(modifier = Modifier.size(48.dp))
            Text("Uploading & parsing…", style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold)
            if (fileName != null) {
                Text(fileName, style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1, overflow = TextOverflow.Ellipsis, textAlign = TextAlign.Center)
            }
        }
    }
}

// ── Parse result banner ────────────────────────────────────────────────────

@Composable
private fun ParseResultBanner(response: StatementUploadResponse, visibleCount: Int) {
    val isParsed = response.status == "parsed"
    val color = if (isParsed) IncomeGreen else NeutralAmber
    FinSightCard(containerColor = color.copy(alpha = 0.08f)) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Icon(
                imageVector = if (isParsed) ImageVector.vectorResource(R.drawable.check_circle)
                              else ImageVector.vectorResource(R.drawable.warning),
                contentDescription = null, tint = color, modifier = Modifier.size(24.dp)
            )
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    if (isParsed) "Statement parsed" else "Parse incomplete",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold, color = color
                )
                Text(
                    "$visibleCount transaction${if (visibleCount != 1) "s" else ""} ready for review  •  ${response.fileName}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

// ── Preview summary: totals ────────────────────────────────────────────────

@Composable
private fun PreviewSummaryRow(totalExpense: Double, totalIncome: Double) {
    FinSightCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            horizontalArrangement = Arrangement.SpaceEvenly
        ) {
            SummaryColumn(label = "Total Expenses", amount = totalExpense, color = ExpenseRed, prefix = "-")
            Box(Modifier.width(1.dp).height(36.dp).background(MaterialTheme.colorScheme.outlineVariant))
            SummaryColumn(label = "Total Income", amount = totalIncome, color = IncomeGreen, prefix = "+")
        }
    }
}

@Composable
private fun SummaryColumn(label: String, amount: Double, color: androidx.compose.ui.graphics.Color, prefix: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(label, style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Text(
            "$prefix\$${String.format(Locale.getDefault(), "%.2f", amount)}",
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.Bold, color = color
        )
    }
}

// ── Preview header ─────────────────────────────────────────────────────────

@Composable
private fun PreviewHeader(visibleCount: Int, removedCount: Int, onRestoreAll: () -> Unit) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically
    ) {
        Text(
            "Preview ($visibleCount)",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold
        )
        if (removedCount > 0) {
            Text(
                "Restore all ($removedCount)",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.primary,
                modifier = Modifier.clickable { onRestoreAll() }
            )
        }
    }
}

// ── Empty preview state ────────────────────────────────────────────────────

@Composable
private fun EmptyPreviewState(onRestoreAll: () -> Unit) {
    FinSightCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(32.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Icon(
                imageVector = ImageVector.vectorResource(R.drawable.receipt),
                contentDescription = null,
                modifier = Modifier.size(40.dp),
                tint = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.4f)
            )
            Text(
                "No transactions selected",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onSurface
            )
            Text(
                "Restore removed transactions or upload another statement.",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center
            )
            OutlinedButton(onClick = onRestoreAll, shape = RoundedCornerShape(10.dp)) {
                Text("Restore All")
            }
        }
    }
}

// ── Transaction row with remove button ────────────────────────────────────

@Composable
private fun ExtractedTransactionRow(
    transaction: ExtractedTransaction,
    onRemove: () -> Unit
) {
    FinSightCard(modifier = Modifier.fillMaxWidth(), containerColor = MaterialTheme.colorScheme.surface) {
        Column {
            Row(
                modifier = Modifier.fillMaxWidth().padding(start = 16.dp, end = 4.dp, top = 12.dp, bottom = 12.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                // Date badge
                Box(
                    modifier = Modifier
                        .background(MaterialTheme.colorScheme.primary.copy(alpha = 0.08f), RoundedCornerShape(8.dp))
                        .padding(horizontal = 8.dp, vertical = 6.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        formatDisplayDate(transaction.transactionDate),
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.primary,
                        fontWeight = FontWeight.Medium
                    )
                }

                // Description
                Text(
                    transaction.description,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurface,
                    modifier = Modifier.weight(1f),
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis
                )

                // Amount
                val isNegative = transaction.amount < 0
                Text(
                    formatAmount(transaction.amount),
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = if (isNegative) ExpenseRed else IncomeGreen
                )

                // Remove button
                IconButton(onClick = onRemove, modifier = Modifier.size(36.dp)) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "Remove transaction",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.size(18.dp)
                    )
                }
            }
            HorizontalDivider(
                modifier = Modifier.padding(horizontal = 16.dp),
                thickness = 0.5.dp,
                color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
            )
        }
    }
}

// ── Parse error card ───────────────────────────────────────────────────────

@Composable
private fun ParseErrorCard(message: String) {
    FinSightCard(containerColor = NeutralAmber.copy(alpha = 0.08f)) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.Top,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Icon(ImageVector.vectorResource(R.drawable.error_outline), null, Modifier.size(20.dp), NeutralAmber)
            Text(message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurface)
        }
    }
}

// ── Import action section ──────────────────────────────────────────────────

@Composable
private fun ImportSection(
    count: Int,
    isImporting: Boolean,
    importError: String?,
    onImport: () -> Unit
) {
    Column(modifier = Modifier.fillMaxWidth(), verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(
            onClick = onImport,
            // Disabled when there is nothing to import or an import is in flight.
            enabled = count > 0 && !isImporting,
            modifier = Modifier.fillMaxWidth().height(52.dp),
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.buttonColors(
                disabledContainerColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.38f),
                disabledContentColor = MaterialTheme.colorScheme.onPrimary.copy(alpha = 0.6f)
            )
        ) {
            if (isImporting) {
                CircularProgressIndicator(
                    modifier = Modifier.size(18.dp),
                    strokeWidth = 2.dp,
                    color = MaterialTheme.colorScheme.onPrimary
                )
                Spacer(Modifier.width(8.dp))
                Text("Importing…", style = MaterialTheme.typography.labelLarge)
            } else {
                Icon(ImageVector.vectorResource(R.drawable.check_circle), null, Modifier.size(18.dp))
                Spacer(Modifier.width(8.dp))
                Text(
                    if (count > 0) "Import $count Transaction${if (count != 1) "s" else ""}"
                    else "No Transactions to Import",
                    style = MaterialTheme.typography.labelLarge
                )
            }
        }

        // Friendly error — the button above doubles as retry.
        if (importError != null) {
            FinSightCard(containerColor = ExpenseRed.copy(alpha = 0.06f)) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Icon(ImageVector.vectorResource(R.drawable.error_outline), null, Modifier.size(18.dp), ExpenseRed)
                    Text(
                        importError,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                }
            }
        }
    }
}

// ── Import success card ────────────────────────────────────────────────────

@Composable
private fun ImportSuccessCard(importedCount: Int, failedCount: Int) {
    FinSightCard(containerColor = IncomeGreen.copy(alpha = 0.08f)) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalAlignment = Alignment.Top,
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Icon(
                imageVector = ImageVector.vectorResource(R.drawable.check_circle),
                contentDescription = null,
                tint = IncomeGreen,
                modifier = Modifier.size(24.dp)
            )
            Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                Text(
                    "Transactions imported successfully",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = IncomeGreen
                )
                Text(
                    "$importedCount transaction${if (importedCount != 1) "s" else ""} imported",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurface
                )
                if (failedCount > 0) {
                    Text(
                        "$failedCount could not be imported",
                        style = MaterialTheme.typography.bodySmall,
                        color = NeutralAmber
                    )
                }
            }
        }
    }
}

// ── Upload error card ──────────────────────────────────────────────────────

@Composable
private fun UploadErrorCard(message: String, fileName: String?, onRetry: () -> Unit, onReset: () -> Unit) {
    FinSightCard(containerColor = ExpenseRed.copy(alpha = 0.06f)) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Icon(ImageVector.vectorResource(R.drawable.error_outline), null, Modifier.size(20.dp), ExpenseRed)
                Column {
                    Text("Upload failed", style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold, color = ExpenseRed)
                    if (fileName != null) {
                        Text(fileName, style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1, overflow = TextOverflow.Ellipsis)
                    }
                    Spacer(Modifier.height(4.dp))
                    Text(message, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurface)
                }
            }
            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = onReset, modifier = Modifier.weight(1f), shape = RoundedCornerShape(10.dp)) {
                    Text("Change File")
                }
                Button(onClick = onRetry, modifier = Modifier.weight(1f), shape = RoundedCornerShape(10.dp)) {
                    Text("Retry")
                }
            }
        }
    }
}

// ── Shared layout helpers ──────────────────────────────────────────────────

@Composable
private fun OrDivider() {
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Box(Modifier.weight(1f).height(1.dp).background(MaterialTheme.colorScheme.outlineVariant))
        Text("or", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Box(Modifier.weight(1f).height(1.dp).background(MaterialTheme.colorScheme.outlineVariant))
    }
}

// ── Formatting ─────────────────────────────────────────────────────────────

private fun formatFileSize(bytes: Long): String = when {
    bytes < 1_024L             -> "$bytes B"
    bytes < 1_024L * 1_024L   -> "${bytes / 1_024L} KB"
    else                       -> String.format(Locale.getDefault(), "%.1f MB", bytes / (1_024.0 * 1_024.0))
}

private fun formatAmount(amount: Double): String {
    val abs = String.format(Locale.getDefault(), "%.2f", kotlin.math.abs(amount))
    return if (amount < 0) "-\$$abs" else "+\$$abs"
}

private fun formatDisplayDate(iso: String): String {
    return try {
        val p = iso.split("-")
        if (p.size < 3) return iso
        val m = mapOf(
            "01" to "Jan", "02" to "Feb", "03" to "Mar", "04" to "Apr",
            "05" to "May", "06" to "Jun", "07" to "Jul", "08" to "Aug",
            "09" to "Sep", "10" to "Oct", "11" to "Nov", "12" to "Dec"
        )
        "${m[p[1]] ?: p[1]} ${p[2].trimStart('0').ifEmpty { "0" }}"
    } catch (e: Exception) {
        iso
    }
}
