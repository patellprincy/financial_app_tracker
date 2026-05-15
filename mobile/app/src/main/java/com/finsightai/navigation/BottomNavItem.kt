package com.finsightai.navigation

import androidx.compose.ui.graphics.vector.ImageVector

// this basically defines how each bottom nav should be
data class BottomNavItem(
    val route: String, //where to navigate when clicked
    val label: String, // name that appears under the icons
    val icon: ImageVector, // outline when unselected
    val selectedIcon: ImageVector // filled when selected
)
