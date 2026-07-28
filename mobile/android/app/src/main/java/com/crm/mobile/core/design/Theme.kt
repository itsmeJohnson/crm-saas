package com.crm.mobile.core.design

import android.app.Activity
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.SideEffect
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat

// ---------------------------------------------------------------------------
// Brand palette — indigo accent on slate neutrals, with a muted-teal tertiary.
// Full tonal families so every M3 role is on-brand (no stock purple leaks) and
// consistent between light and dark.
// ---------------------------------------------------------------------------

private object Ind {   // indigo primary tones
    val t20 = Color(0xFF1A1F6B); val t30 = Color(0xFF2E38A6)
    val t40 = Color(0xFF4B56D6); val t80 = Color(0xFFBAC0FF); val t90 = Color(0xFFE0E2FB)
}
private object Slate { // neutral tones
    val t10 = Color(0xFF1B1F2A); val t20 = Color(0xFF2B303C); val t30 = Color(0xFF474C5B)
    val t60 = Color(0xFF8C90A0); val t80 = Color(0xFFC3C7D6); val t90 = Color(0xFFDDE1EC)
}
private object Teal {  // tertiary tones
    val t20 = Color(0xFF00363F); val t30 = Color(0xFF104E59)
    val t40 = Color(0xFF2E7D8F); val t80 = Color(0xFF8FD0DE); val t90 = Color(0xFFACE9F7)
}

private val LightColors = lightColorScheme(
    primary = Ind.t40,
    onPrimary = Color.White,
    primaryContainer = Ind.t90,
    onPrimaryContainer = Ind.t20,
    inversePrimary = Ind.t80,

    secondary = Color(0xFF5A607D),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFDDE1F3),
    onSecondaryContainer = Color(0xFF171B2C),

    tertiary = Teal.t40,
    onTertiary = Color.White,
    tertiaryContainer = Teal.t90,
    onTertiaryContainer = Teal.t20,

    background = Color(0xFFF5F6FA),
    onBackground = Slate.t10,
    surface = Color(0xFFFFFFFF),
    onSurface = Slate.t10,
    surfaceVariant = Color(0xFFE3E6F0),
    onSurfaceVariant = Slate.t30,
    surfaceTint = Ind.t40,

    surfaceContainerLowest = Color(0xFFFFFFFF),
    surfaceContainerLow = Color(0xFFF7F8FC),
    surfaceContainer = Color(0xFFF1F3F9),
    surfaceContainerHigh = Color(0xFFEBEEF6),
    surfaceContainerHighest = Color(0xFFE5E9F3),

    outline = Color(0xFFC3C8D6),
    outlineVariant = Color(0xFFDBDFEA),

    error = Color(0xFFD92D36),
    onError = Color.White,
    errorContainer = Color(0xFFFCDCDE),
    onErrorContainer = Color(0xFF410007),

    inverseSurface = Slate.t20,
    inverseOnSurface = Color(0xFFF0F1F6),
    scrim = Color(0xFF000000),
)

private val DarkColors = darkColorScheme(
    primary = Ind.t80,
    onPrimary = Ind.t20,
    primaryContainer = Ind.t30,
    onPrimaryContainer = Ind.t90,
    inversePrimary = Ind.t40,

    secondary = Color(0xFFC2C6E0),
    onSecondary = Color(0xFF2B3048),
    secondaryContainer = Color(0xFF424764),
    onSecondaryContainer = Color(0xFFDDE1F3),

    tertiary = Teal.t80,
    onTertiary = Teal.t20,
    tertiaryContainer = Teal.t30,
    onTertiaryContainer = Teal.t90,

    background = Color(0xFF0D1017),
    onBackground = Color(0xFFE7EAF3),
    surface = Color(0xFF12151D),
    onSurface = Color(0xFFE7EAF3),
    surfaceVariant = Color(0xFF434758),
    onSurfaceVariant = Slate.t80,
    surfaceTint = Ind.t80,

    surfaceContainerLowest = Color(0xFF080A10),
    surfaceContainerLow = Color(0xFF151A24),
    surfaceContainer = Color(0xFF191E28),
    surfaceContainerHigh = Color(0xFF232936),
    surfaceContainerHighest = Color(0xFF2D3341),

    outline = Slate.t60,
    outlineVariant = Color(0xFF434758),

    error = Color(0xFFFF6168),
    onError = Color(0xFF680007),
    errorContainer = Color(0xFF93000D),
    onErrorContainer = Color(0xFFFFDAD8),

    inverseSurface = Color(0xFFE7EAF3),
    inverseOnSurface = Slate.t20,
    scrim = Color(0xFF000000),
)

// ---------------------------------------------------------------------------
// Typography — system font, tuned weights + tracking for a cleaner, denser feel.
// ---------------------------------------------------------------------------

private val AppTypography = Typography().run {
    copy(
        headlineMedium = headlineMedium.copy(fontWeight = FontWeight.SemiBold, letterSpacing = (-0.5).sp),
        headlineSmall = headlineSmall.copy(fontWeight = FontWeight.SemiBold, letterSpacing = (-0.25).sp),
        titleLarge = titleLarge.copy(fontWeight = FontWeight.SemiBold),
        titleMedium = titleMedium.copy(fontWeight = FontWeight.SemiBold),
        titleSmall = titleSmall.copy(fontWeight = FontWeight.SemiBold),
        labelLarge = labelLarge.copy(fontWeight = FontWeight.Medium, letterSpacing = 0.1.sp),
        labelMedium = labelMedium.copy(fontWeight = FontWeight.Medium),
        bodyLarge = bodyLarge.copy(lineHeight = 22.sp),
        bodyMedium = bodyMedium.copy(lineHeight = 20.sp, letterSpacing = 0.1.sp),
    )
}

// ---------------------------------------------------------------------------
// Shapes — slightly rounder than M3 defaults for a modern card language.
// ---------------------------------------------------------------------------

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(6.dp),
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(14.dp),
    large = RoundedCornerShape(20.dp),
    extraLarge = RoundedCornerShape(28.dp),
)

@Composable
fun CrmTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colorScheme = if (darkTheme) DarkColors else LightColors

    // Tint the system status bar to match the app background (instead of the
    // stock grey) and flip the icon contrast for the active theme.
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as Activity).window
            window.statusBarColor = colorScheme.background.toArgb()
            WindowCompat.getInsetsController(window, view).isAppearanceLightStatusBars = !darkTheme
        }
    }

    MaterialTheme(
        colorScheme = colorScheme,
        typography = AppTypography,
        shapes = AppShapes,
        content = content,
    )
}
