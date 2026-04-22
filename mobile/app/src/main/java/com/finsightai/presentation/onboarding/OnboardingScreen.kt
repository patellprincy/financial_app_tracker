package com.finsightai.presentation.onboarding

import androidx.compose.animation.AnimatedContent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.vectorResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import com.finsightai.R
import com.finsightai.ui.components.PrimaryButton

data class OnboardingPage(
    val icon: ImageVector,
    val title: String,
    val subtitle: String
)

@Composable
private fun onboardingPages(): List<OnboardingPage> {
    return listOf(
        OnboardingPage(
            icon = ImageVector.vectorResource(id = R.drawable.cloud_upload),
            title = "Upload Your Statements",
            subtitle = "Import CSV files from any bank or card and we'll organize everything automatically"
        ),
        OnboardingPage(
            icon = ImageVector.vectorResource(id = R.drawable.insights),
            title = "Understand Your Spending",
            subtitle = "Get clear insights on where your money goes — no jargon, just plain English"
        ),
        OnboardingPage(
            icon = ImageVector.vectorResource(id = R.drawable.chat),
            title = "Ask Anything",
            subtitle = "Chat with your AI assistant to get personalized answers about your finances"
        )
    )
}

@Composable
fun OnboardingScreen(onNavigateToLogin: () -> Unit) {
    var currentPage by remember { mutableIntStateOf(0) }
    val pages = onboardingPages()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(MaterialTheme.colorScheme.background)
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Spacer(modifier = Modifier.height(48.dp))

        AnimatedContent(targetState = currentPage, label = "onboarding") { page ->
            OnboardingPageContent(pages[page])
        }

        Spacer(modifier = Modifier.weight(1f))

        Row(
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            pages.indices.forEach { index ->
                Box(
                    modifier = Modifier
                        .size(if (index == currentPage) 24.dp else 8.dp, 8.dp)
                        .background(
                            color = if (index == currentPage) MaterialTheme.colorScheme.primary
                            else MaterialTheme.colorScheme.onSurface.copy(alpha = 0.2f),
                            shape = CircleShape
                        )
                )
            }
        }

        Spacer(modifier = Modifier.height(32.dp))

        PrimaryButton(
            text = if (currentPage < pages.lastIndex) "Next" else "Get Started",
            onClick = {
                if (currentPage < pages.lastIndex) {
                    currentPage++
                } else {
                    onNavigateToLogin()
                }
            }
        )

        Spacer(modifier = Modifier.height(16.dp))

        if (currentPage < pages.lastIndex) {
            OutlinedButton(
                onClick = onNavigateToLogin,
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Skip")
            }
        }

        Spacer(modifier = Modifier.height(24.dp))
    }
}

@Composable
private fun OnboardingPageContent(page: OnboardingPage) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        modifier = Modifier.padding(horizontal = 8.dp)
    ) {
        Box(
            modifier = Modifier
                .size(120.dp)
                .background(
                    color = MaterialTheme.colorScheme.primary.copy(alpha = 0.1f),
                    shape = CircleShape
                ),
            contentAlignment = Alignment.Center
        ) {
            Icon(
                imageVector = page.icon,
                contentDescription = null,
                modifier = Modifier.size(56.dp),
                tint = MaterialTheme.colorScheme.primary
            )
        }
        Spacer(modifier = Modifier.height(32.dp))
        Text(
            text = page.title,
            style = MaterialTheme.typography.headlineMedium,
            color = MaterialTheme.colorScheme.onBackground,
            textAlign = TextAlign.Center
        )
        Spacer(modifier = Modifier.height(12.dp))
        Text(
            text = page.subtitle,
            style = MaterialTheme.typography.bodyLarge,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center
        )
    }
}
