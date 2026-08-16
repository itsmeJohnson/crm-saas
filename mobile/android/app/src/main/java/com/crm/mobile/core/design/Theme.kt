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
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat

// ---------------------------------------------------------------------------
// Minimalist Dental Palette — Pure clinical teal/cyan accents on soft slate neutrals.
// Engineered for dental practice clarity, minimal eye-strain, and rapid scanning.
// ---------------------------------------------------------------------------

object DentalColors {
    // Primary Dental Teal tones
    val Teal50 = Color(0xFFF0FDFA)
    val Teal100 = Color(0xFFCCFBF1)
    val Teal200 = Color(0xFF99F6E4)
    val Teal500 = Color(0xFF14B8A6)
    val Teal600 = Color(0xFF0D9488)
    val Teal700 = Color(0xFF0F766E)
    val Teal900 = Color(0xFF134E4A)

    // Slate neutrals
    val Slate900 = Color(0xFF0F172A)
    val Slate800 = Color(0xFF1E293B)
    val Slate700 = Color(0xFF334155)
    val Slate600 = Color(0xFF475569)
    val Slate500 = Color(0xFF64748B)
    val Slate400 = Color(0xFF94A3B8)
    val Slate200 = Color(0xFFE2E8F0)
    val Slate100 = Color(0xFFF1F5F9)
    val Slate50 = Color(0xFFF8FAFC)

    // Clinical Status & Badges
    val StatusHealthy = Color(0xFF10B981) // Mint green
    val StatusHealthyBg = Color(0xFFD1FAE5)
    val StatusCaries = Color(0xFFEF4444) // Coral red
    val StatusCariesBg = Color(0xFFFEE2E2)
    val StatusCrown = Color(0xFFF59E0B) // Amber gold
    val StatusCrownBg = Color(0xFFFEF3C7)
    val StatusRCT = Color(0xFF8B5CF6) // Royal Purple
    val StatusRCTBg = Color(0xFFEDE9FE)
    val StatusImplant = Color(0xFF0284C7) // Sky blue
    val StatusImplantBg = Color(0xFFE0F2FE)
    val StatusMissing = Color(0xFF94A3B8) // Muted gray
    val StatusMissingBg = Color(0xFFF1F5F9)
}

private val LightColors = lightColorScheme(
    primary = DentalColors.Teal600,
    onPrimary = Color.White,
    primaryContainer = DentalColors.Teal100,
    onPrimaryContainer = DentalColors.Teal900,
    inversePrimary = DentalColors.Teal200,

    secondary = Color(0xFF0284C7),
    onSecondary = Color.White,
    secondaryContainer = Color(0xFFE0F2FE),
    onSecondaryContainer = Color(0xFF0369A1),

    tertiary = Color(0xFF6366F1),
    onTertiary = Color.White,
    tertiaryContainer = Color(0xFFEEF2FF),
    onTertiaryContainer = Color(0xFF312E81),

    background = DentalColors.Slate50,
    onBackground = DentalColors.Slate900,
    surface = Color(0xFFFFFFFF),
    onSurface = DentalColors.Slate900,
    surfaceVariant = DentalColors.Slate100,
    onSurfaceVariant = DentalColors.Slate600,
    surfaceTint = DentalColors.Teal600,

    surfaceContainerLowest = Color(0xFFFFFFFF),
    surfaceContainerLow = Color(0xFFF8FAFC),
    surfaceContainer = Color(0xFFF1F5F9),
    surfaceContainerHigh = Color(0xFFE2E8F0),
    surfaceContainerHighest = Color(0xFFCBD5E1),

    outline = DentalColors.Slate200,
    outlineVariant = Color(0xFFE2E8F0),

    error = Color(0xFFE11D48),
    onError = Color.White,
    errorContainer = Color(0xFFFFE4E6),
    onErrorContainer = Color(0xFF881337),

    inverseSurface = DentalColors.Slate800,
    inverseOnSurface = DentalColors.Slate50,
    scrim = Color(0xFF000000),
)

private val DarkColors = darkColorScheme(
    primary = DentalColors.Teal200,
    onPrimary = DentalColors.Teal900,
    primaryContainer = DentalColors.Teal700,
    onPrimaryContainer = DentalColors.Teal100,
    inversePrimary = DentalColors.Teal600,

    secondary = Color(0xFF7DD3FC),
    onSecondary = Color(0xFF082F49),
    secondaryContainer = Color(0xFF0369A1),
    onSecondaryContainer = Color(0xFFE0F2FE),

    tertiary = Color(0xFFA5B4FC),
    onTertiary = Color(0xFF1E1B4B),
    tertiaryContainer = Color(0xFF3730A3),
    onTertiaryContainer = Color(0xFFEEF2FF),

    background = Color(0xFF0B0F19),
    onBackground = Color(0xFFF8FAFC),
    surface = Color(0xFF111827),
    onSurface = Color(0xFFF8FAFC),
    surfaceVariant = Color(0xFF1F2937),
    onSurfaceVariant = DentalColors.Slate400,
    surfaceTint = DentalColors.Teal200,

    surfaceContainerLowest = Color(0xFF080C14),
    surfaceContainerLow = Color(0xFF131B2E),
    surfaceContainer = Color(0xFF182238),
    surfaceContainerHigh = Color(0xFF222F4C),
    surfaceContainerHighest = Color(0xFF2D3C5E),

    outline = DentalColors.Slate700,
    outlineVariant = Color(0xFF334155),

    error = Color(0xFFFB7185),
    onError = Color(0xFF4C0519),
    errorContainer = Color(0xFF881337),
    onErrorContainer = Color(0xFFFFE4E6),

    inverseSurface = Color(0xFFF8FAFC),
    inverseOnSurface = DentalColors.Slate800,
    scrim = Color(0xFF000000),
)

private val AppTypography = Typography(
    headlineLarge = TextStyle(fontWeight = FontWeight.Bold, fontSize = 28.sp, letterSpacing = (-0.5).sp),
    headlineMedium = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 22.sp, letterSpacing = (-0.3).sp),
    headlineSmall = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 18.sp, letterSpacing = (-0.2).sp),
    titleLarge = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 16.sp, letterSpacing = (-0.1).sp),
    titleMedium = TextStyle(fontWeight = FontWeight.Medium, fontSize = 14.sp, letterSpacing = 0.sp),
    titleSmall = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 12.sp, letterSpacing = 0.1.sp),
    bodyLarge = TextStyle(fontWeight = FontWeight.Normal, fontSize = 15.sp, lineHeight = 22.sp),
    bodyMedium = TextStyle(fontWeight = FontWeight.Normal, fontSize = 13.sp, lineHeight = 19.sp, letterSpacing = 0.1.sp),
    bodySmall = TextStyle(fontWeight = FontWeight.Normal, fontSize = 11.sp, lineHeight = 15.sp),
    labelLarge = TextStyle(fontWeight = FontWeight.SemiBold, fontSize = 13.sp, letterSpacing = 0.2.sp),
    labelMedium = TextStyle(fontWeight = FontWeight.Medium, fontSize = 11.sp, letterSpacing = 0.2.sp),
    labelSmall = TextStyle(fontWeight = FontWeight.Medium, fontSize = 10.sp, letterSpacing = 0.3.sp),
)

private val AppShapes = Shapes(
    extraSmall = RoundedCornerShape(8.dp),
    small = RoundedCornerShape(12.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(22.dp),
    extraLarge = RoundedCornerShape(30.dp),
)

@Composable
fun CrmTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colorScheme = if (darkTheme) DarkColors else LightColors

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
