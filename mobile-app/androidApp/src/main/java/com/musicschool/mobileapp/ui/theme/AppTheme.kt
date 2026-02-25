package com.musicschool.mobileapp.ui.theme

import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Mapped from website CSS palette:
// style.css accent #6b4eff, accent2 #ffcc66
// student.css primary #ff8f3d, teacher/admin #18a957
private val LightColors = lightColorScheme(
    primary = Color(0xFF6B4EFF),
    onPrimary = Color(0xFFFFFFFF),
    secondary = Color(0xFFFFCC66),
    onSecondary = Color(0xFF3A2000),
    tertiary = Color(0xFF18A957),
    background = Color(0xFFFBFBFE),
    onBackground = Color(0xFF101018),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF101018),
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF8F78FF),
    onPrimary = Color(0xFF140F3A),
    secondary = Color(0xFFFFD98C),
    tertiary = Color(0xFF48C878),
    background = Color(0xFF0E1018),
    onBackground = Color(0xFFEDEBFF),
    surface = Color(0xFF151824),
    onSurface = Color(0xFFEDEBFF),
)

@Composable
fun MusicSchoolTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = LightColors,
        typography = MaterialTheme.typography,
        content = content,
    )
}
