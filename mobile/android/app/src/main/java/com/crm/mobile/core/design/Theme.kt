package com.crm.mobile.core.design

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// Brand tokens carried from the web CRM: indigo accent on slate neutrals.
private val Indigo = Color(0xFF4B56D6)
private val IndigoLight = Color(0xFF7E88F0)

private val LightColors = lightColorScheme(
    primary = Indigo,
    onPrimary = Color.White,
    background = Color(0xFFF5F6FA),
    surface = Color(0xFFFFFFFF),
    onSurface = Color(0xFF1B1F2A),
    surfaceVariant = Color(0xFFEEF0F6),
    error = Color(0xFFD92D36),
)

private val DarkColors = darkColorScheme(
    primary = IndigoLight,
    onPrimary = Color(0xFF10131C),
    background = Color(0xFF0D1017),
    surface = Color(0xFF151A24),
    onSurface = Color(0xFFE7EAF3),
    surfaceVariant = Color(0xFF1C2230),
    error = Color(0xFFFF6168),
)

@Composable
fun CrmTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = if (darkTheme) DarkColors else LightColors,
        content = content,
    )
}
