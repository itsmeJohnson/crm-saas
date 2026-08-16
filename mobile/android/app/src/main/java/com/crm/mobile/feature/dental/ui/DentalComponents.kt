package com.crm.mobile.feature.dental.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Divider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.crm.mobile.core.design.DentalColors
import com.crm.mobile.feature.dental.AppointmentStatus
import com.crm.mobile.feature.dental.ToothCondition
import com.crm.mobile.feature.dental.ToothStatus

@Composable
fun MinimalCard(
    modifier: Modifier = Modifier,
    onClick: (() -> Unit)? = null,
    containerColor: Color = MaterialTheme.colorScheme.surface,
    borderColor: Color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f),
    content: @Composable () -> Unit
) {
    Card(
        modifier = modifier
            .fillMaxWidth()
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = containerColor),
        border = CardDefaults.outlinedCardBorder().copy(brush = androidx.compose.ui.graphics.SolidColor(borderColor))
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            content()
        }
    }
}

@Composable
fun DentalMetricPill(
    title: String,
    value: String,
    badgeText: String? = null,
    accentColor: Color = DentalColors.Teal600,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(14.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = CardDefaults.outlinedCardBorder().copy(brush = androidx.compose.ui.graphics.SolidColor(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f)))
    ) {
        Column(modifier = Modifier.padding(12.dp)) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (badgeText != null) {
                    Box(
                        modifier = Modifier
                            .background(accentColor.copy(alpha = 0.12f), RoundedCornerShape(6.dp))
                            .padding(horizontal = 6.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = badgeText,
                            style = MaterialTheme.typography.labelSmall.copy(fontSize = 9.sp),
                            color = accentColor,
                            fontWeight = FontWeight.Bold
                        )
                    }
                }
            }
            Spacer(modifier = Modifier.height(4.dp))
            Text(
                text = value,
                style = MaterialTheme.typography.titleLarge.copy(fontSize = 18.sp),
                color = MaterialTheme.colorScheme.onSurface,
                fontWeight = FontWeight.Bold
            )
        }
    }
}

@Composable
fun DentalStatusBadge(
    status: AppointmentStatus,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .background(status.bgColor, RoundedCornerShape(8.dp))
            .padding(horizontal = 8.dp, vertical = 4.dp)
    ) {
        Text(
            text = status.label,
            style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.SemiBold),
            color = status.color
        )
    }
}

@Composable
fun MedicalAlertBadge(
    alert: String,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .background(Color(0xFFFFE4E6), RoundedCornerShape(6.dp))
            .border(1.dp, Color(0xFFFDA4AF), RoundedCornerShape(6.dp))
            .padding(horizontal = 8.dp, vertical = 3.dp)
    ) {
        Text(
            text = "⚠ $alert",
            style = MaterialTheme.typography.labelSmall.copy(fontSize = 11.sp, fontWeight = FontWeight.Bold),
            color = Color(0xFFBE123C)
        )
    }
}

@Composable
fun QuickActionCircle(
    iconText: String,
    label: String,
    onClick: () -> Unit,
    accentColor: Color = DentalColors.Teal600,
    modifier: Modifier = Modifier
) {
    Column(
        modifier = modifier
            .clickable(onClick = onClick)
            .padding(vertical = 4.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Box(
            modifier = Modifier
                .size(46.dp)
                .background(accentColor.copy(alpha = 0.1f), CircleShape)
                .border(1.dp, accentColor.copy(alpha = 0.3f), CircleShape),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = iconText,
                fontSize = 18.sp,
                textAlign = TextAlign.Center
            )
        }
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = label,
            style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
            color = MaterialTheme.colorScheme.onSurface,
            fontWeight = FontWeight.Medium,
            textAlign = TextAlign.Center,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis
        )
    }
}

// ---------------------------------------------------------------------------
// Visual Interactive Odontogram Chart (FDI Notation 11-48)
// ---------------------------------------------------------------------------

@Composable
fun VisualOdontogramChart(
    teethMap: Map<Int, ToothCondition>,
    onToothClick: (Int, ToothCondition?) -> Unit,
    modifier: Modifier = Modifier
) {
    // Upper Arch (Maxillary): Q1 (18-11) right to left, Q2 (21-28) left to right
    val upperRight = (18 downTo 11).toList()
    val upperLeft = (21..28).toList()

    // Lower Arch (Mandibular): Q4 (48-41) right to left, Q3 (31-38) left to right
    val lowerRight = (48 downTo 41).toList()
    val lowerLeft = (31..38).toList()

    Column(
        modifier = modifier
            .fillMaxWidth()
            .background(MaterialTheme.colorScheme.surface, RoundedCornerShape(16.dp))
            .border(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f), RoundedCornerShape(16.dp))
            .padding(14.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "🦷 Visual Odontogram (FDI Chart)",
                style = MaterialTheme.typography.titleMedium,
                color = MaterialTheme.colorScheme.onSurface,
                fontWeight = FontWeight.SemiBold
            )
            Text(
                text = "Tap tooth to chart",
                style = MaterialTheme.typography.labelSmall,
                color = DentalColors.Teal600
            )
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Upper Jaw label
        Text(
            text = "UPPER ARCH (MAXILLARY)",
            style = MaterialTheme.typography.labelSmall.copy(letterSpacing = 1.sp),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.fillMaxWidth(),
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(6.dp))

        // Upper Arch Row (Scrollable horizontally for high-density touch targets)
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.Center
        ) {
            // Upper Right Q1
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                upperRight.forEach { toothNum ->
                    ToothItemView(
                        toothNumber = toothNum,
                        condition = teethMap[toothNum],
                        onClick = { onToothClick(toothNum, teethMap[toothNum]) }
                    )
                }
            }
            Spacer(modifier = Modifier.width(10.dp))
            Box(
                modifier = Modifier
                    .width(1.dp)
                    .height(54.dp)
                    .background(MaterialTheme.colorScheme.outlineVariant)
            )
            Spacer(modifier = Modifier.width(10.dp))
            // Upper Left Q2
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                upperLeft.forEach { toothNum ->
                    ToothItemView(
                        toothNumber = toothNum,
                        condition = teethMap[toothNum],
                        onClick = { onToothClick(toothNum, teethMap[toothNum]) }
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(10.dp))
        Divider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
        Spacer(modifier = Modifier.height(10.dp))

        // Lower Arch Row
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.Center
        ) {
            // Lower Right Q4
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                lowerRight.forEach { toothNum ->
                    ToothItemView(
                        toothNumber = toothNum,
                        condition = teethMap[toothNum],
                        onClick = { onToothClick(toothNum, teethMap[toothNum]) }
                    )
                }
            }
            Spacer(modifier = Modifier.width(10.dp))
            Box(
                modifier = Modifier
                    .width(1.dp)
                    .height(54.dp)
                    .background(MaterialTheme.colorScheme.outlineVariant)
            )
            Spacer(modifier = Modifier.width(10.dp))
            // Lower Left Q3
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                lowerLeft.forEach { toothNum ->
                    ToothItemView(
                        toothNumber = toothNum,
                        condition = teethMap[toothNum],
                        onClick = { onToothClick(toothNum, teethMap[toothNum]) }
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(6.dp))
        Text(
            text = "LOWER ARCH (MANDIBULAR)",
            style = MaterialTheme.typography.labelSmall.copy(letterSpacing = 1.sp),
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.fillMaxWidth(),
            textAlign = TextAlign.Center
        )

        Spacer(modifier = Modifier.height(12.dp))

        // Legend
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            ToothStatus.values().take(6).forEach { status ->
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(10.dp)
                            .background(status.color, CircleShape)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        text = status.label,
                        style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        }
    }
}

@Composable
fun ToothItemView(
    toothNumber: Int,
    condition: ToothCondition?,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    val toothStatus = condition?.getToothStatus() ?: ToothStatus.HEALTHY
    val isTreatedOrAlert = toothStatus != ToothStatus.HEALTHY

    Column(
        modifier = modifier
            .width(36.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(if (isTreatedOrAlert) toothStatus.bgColor else MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f))
            .border(
                1.dp,
                if (isTreatedOrAlert) toothStatus.color else MaterialTheme.colorScheme.outlineVariant,
                RoundedCornerShape(8.dp)
            )
            .clickable(onClick = onClick)
            .padding(vertical = 6.dp, horizontal = 2.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Text(
            text = toothNumber.toString(),
            style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp, fontWeight = FontWeight.Bold),
            color = if (isTreatedOrAlert) toothStatus.color else MaterialTheme.colorScheme.onSurface
        )
        Spacer(modifier = Modifier.height(3.dp))
        Box(
            modifier = Modifier
                .size(14.dp)
                .background(toothStatus.color, RoundedCornerShape(3.dp)),
            contentAlignment = Alignment.Center
        ) {
            Text(
                text = when (toothStatus) {
                    ToothStatus.HEALTHY -> "✓"
                    ToothStatus.CARIES -> "✕"
                    ToothStatus.RCT -> "R"
                    ToothStatus.CROWN -> "C"
                    ToothStatus.IMPLANT -> "I"
                    ToothStatus.MISSING -> "—"
                    ToothStatus.FILLING -> "F"
                    ToothStatus.BRIDGE -> "B"
                },
                fontSize = 8.sp,
                fontWeight = FontWeight.Bold,
                color = Color.White
            )
        }
    }
}
