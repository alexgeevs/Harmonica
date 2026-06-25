package com.harmonica.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Harmonica palette: deep green + teal accent.
private val Teal = Color(0xFF206A5D)
private val DeepGreen = Color(0xFF20302F)
private val Mint = Color(0xFFEEF3F1)

private val LightColors = lightColorScheme(
    primary = Teal,
    secondary = DeepGreen,
    background = Mint
)

private val DarkColors = darkColorScheme(
    primary = Color(0xFF6FCAA9),
    secondary = Color(0xFFA8D8C1),
    background = DeepGreen
)

@Composable
fun HarmonicaTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = if (isSystemInDarkTheme()) DarkColors else LightColors,
        content = content
    )
}
