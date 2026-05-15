package com.finsightai.navigation

import android.util.Log
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.navigation.NavHostController
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.navArgument
import com.finsightai.core.AppAuthState
import com.finsightai.presentation.addexpense.AddExpenseScreen
import com.finsightai.presentation.auth.LoginScreen
import com.finsightai.presentation.auth.SignUpScreen
import com.finsightai.presentation.chat.ChatScreen
import com.finsightai.presentation.home.HomeScreen
import com.finsightai.presentation.insights.InsightsScreen
import com.finsightai.presentation.onboarding.OnboardingScreen
import com.finsightai.presentation.settings.SettingsScreen
import com.finsightai.presentation.splash.SplashScreen
import com.finsightai.presentation.transactions.TransactionDetailScreen
import com.finsightai.presentation.transactions.TransactionsScreen
import com.finsightai.presentation.upload.UploadScreen

@Composable
fun AppNavGraph(navController: NavHostController) {
    // Global session expiry handler: any 401/403 on an authenticated request clears
    // the session (done in AuthInterceptor) and lands here to wipe the back stack.
    LaunchedEffect(Unit) {
        AppAuthState.unauthorizedEvent.collect {
            Log.d("AppNavGraph", "unauthorizedEvent — clearing back stack and navigating to Login")
            navController.navigate(NavRoutes.Login.route) {
                popUpTo(0) { inclusive = true }
            }
        }
    }

    NavHost(
        navController = navController,
        startDestination = NavRoutes.Splash.route
    ) {
        composable(NavRoutes.Splash.route) {
            SplashScreen(
                onNavigateToOnboarding = {
                    navController.navigate(NavRoutes.Onboarding.route) {
                        popUpTo(NavRoutes.Splash.route) { inclusive = true }
                    }
                },
                onNavigateToHome = {
                    navController.navigate(NavRoutes.Home.route) {
                        popUpTo(NavRoutes.Splash.route) { inclusive = true }
                    }
                },
                onNavigateToLogin = {
                    navController.navigate(NavRoutes.Login.route) {
                        popUpTo(NavRoutes.Splash.route) { inclusive = true }
                    }
                }
            )
        }

        composable(NavRoutes.Onboarding.route) {
            OnboardingScreen(
                onNavigateToLogin = {
                    navController.navigate(NavRoutes.Login.route) {
                        popUpTo(NavRoutes.Onboarding.route) { inclusive = true }
                    }
                }
            )
        }

        composable(NavRoutes.Login.route) {
            LoginScreen(
                onNavigateToHome = {
                    navController.navigate(NavRoutes.Home.route) {
                        popUpTo(NavRoutes.Login.route) { inclusive = true }
                    }
                },
                onNavigateToSignUp = {
                    navController.navigate(NavRoutes.SignUp.route)
                }
            )
        }

        composable(NavRoutes.SignUp.route) {
            SignUpScreen(
                onNavigateToHome = {
                    navController.navigate(NavRoutes.Home.route) {
                        popUpTo(NavRoutes.SignUp.route) { inclusive = true }
                    }
                },
                onNavigateBack = {
                    navController.popBackStack()
                }
            )
        }

        composable(NavRoutes.Home.route) {
            HomeScreen(
                onNavigateToTransactions = { navController.navigate(NavRoutes.Transactions.route) },
                onNavigateToUpload = { navController.navigate(NavRoutes.Upload.route) },
                onNavigateToAddExpense = { navController.navigate(NavRoutes.AddExpense.route) },
                onNavigateToChat = { navController.navigate(NavRoutes.Chat.route) },
                onNavigateToSettings = { navController.navigate(NavRoutes.Settings.route) },
                navController = navController
            )
        }

        composable(NavRoutes.Transactions.route) {
            TransactionsScreen(
                onNavigateToDetail = { transactionId ->
                    navController.navigate(NavRoutes.TransactionDetail.createRoute(transactionId))
                },
                navController = navController
            )
        }

        composable(
            route = NavRoutes.TransactionDetail.route,
            arguments = listOf(navArgument("transactionId") { type = NavType.StringType })
        ) { backStackEntry ->
            val transactionId = backStackEntry.arguments?.getString("transactionId") ?: ""
            TransactionDetailScreen(
                transactionId = transactionId,
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(NavRoutes.Upload.route) {
            UploadScreen(
                onNavigateToAddExpense = { navController.navigate(NavRoutes.AddExpense.route) },
                navController = navController
            )
        }

        composable(NavRoutes.Insights.route) {
            InsightsScreen(navController = navController)
        }

        composable(NavRoutes.Chat.route) {
            ChatScreen(navController = navController)
        }

        composable(NavRoutes.Settings.route) {
            SettingsScreen(
                onNavigateToLogin = {
                    navController.navigate(NavRoutes.Login.route) {
                        popUpTo(0) { inclusive = true }
                    }
                },
                onNavigateBack = { navController.popBackStack() }
            )
        }

        composable(NavRoutes.AddExpense.route) {
            AddExpenseScreen(
                onNavigateBack = { navController.popBackStack() },
                onSaveSuccess = {
                    navController.previousBackStackEntry
                        ?.savedStateHandle
                        ?.set("transactionSaved", true)
                    navController.popBackStack()
                }
            )
        }
    }
}
