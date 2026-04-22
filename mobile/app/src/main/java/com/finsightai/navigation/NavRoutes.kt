package com.finsightai.navigation

import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.vectorResource
import com.finsightai.R

sealed class NavRoutes(val route: String) {
    data object Splash : NavRoutes("splash")
    data object Onboarding : NavRoutes("onboarding")
    data object Login : NavRoutes("login")
    data object SignUp : NavRoutes("signup")
    data object Home : NavRoutes("home")
    data object Transactions : NavRoutes("transactions")
    data object TransactionDetail : NavRoutes("transaction_detail/{transactionId}") {
        fun createRoute(transactionId: String) = "transaction_detail/$transactionId"
    }
    data object Upload : NavRoutes("upload")
    data object Insights : NavRoutes("insights")
    data object Chat : NavRoutes("chat")
    data object Settings : NavRoutes("settings")
    data object AddExpense : NavRoutes("add_expense")
}

@Composable
fun bottomNavItems(): List<BottomNavItem> {
    return listOf(
        BottomNavItem(
            route = NavRoutes.Home.route,
            label = "Home",
            icon = ImageVector.vectorResource(R.drawable.home),
            selectedIcon = ImageVector.vectorResource(R.drawable.home)
        ),
        BottomNavItem(
            route = NavRoutes.Transactions.route,
            label = "Transactions",
            icon = ImageVector.vectorResource(R.drawable.receipt),
            selectedIcon = ImageVector.vectorResource(R.drawable.receipt)
        ),
        BottomNavItem(
            route = NavRoutes.Upload.route,
            label = "Upload",
            icon = ImageVector.vectorResource(R.drawable.cloud_upload),
            selectedIcon = ImageVector.vectorResource(R.drawable.cloud_upload)
        ),
        BottomNavItem(
            route = NavRoutes.Insights.route,
            label = "Insights",
            icon = ImageVector.vectorResource(R.drawable.insights),
            selectedIcon = ImageVector.vectorResource(R.drawable.insights)
        ),
        BottomNavItem(
            route = NavRoutes.Chat.route,
            label = "Chat",
            icon = ImageVector.vectorResource(R.drawable.chat),
            selectedIcon = ImageVector.vectorResource(R.drawable.chat)
        )
    )
}
