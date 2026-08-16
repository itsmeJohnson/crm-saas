package com.crm.mobile.feature.dental.ui

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Divider
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.crm.mobile.core.design.DentalColors
import com.crm.mobile.feature.dental.DentalRecall
import com.crm.mobile.feature.dental.DentalRepository

@Composable
fun DentalRecallsAnalyticsScreen(
    repository: DentalRepository,
    onLogout: () -> Unit
) {
    val context = LocalContext.current
    val recalls by repository.recalls.collectAsState()

    Scaffold(
        topBar = {
            Surface(
                color = MaterialTheme.colorScheme.surface,
                border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Text(
                        text = "🔔 Patient Recalls & Operations Hub",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Text(
                        text = "Automated preventive hygiene recalls and practice metrics",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            item { Spacer(modifier = Modifier.height(4.dp)) }

            // 1. Recall Dispatch Summary
            item {
                MinimalCard(
                    containerColor = DentalColors.Teal50,
                    borderColor = DentalColors.Teal200
                ) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = "1-Click WhatsApp Recalls",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = DentalColors.Teal900
                            )
                            Text(
                                text = "${recalls.count { it.status == "PENDING" }} patients due for preventive dental checkups",
                                style = MaterialTheme.typography.bodySmall,
                                color = DentalColors.Teal700
                            )
                        }
                        Box(
                            modifier = Modifier
                                .size(40.dp)
                                .background(DentalColors.Teal100, CircleShape),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("💬", fontSize = 18.sp)
                        }
                    }
                }
            }

            item {
                Text(
                    text = "Scheduled Recalls (${recalls.size})",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }

            items(recalls) { recall ->
                DentalRecallItemCard(
                    recall = recall,
                    onSendWhatsApp = {
                        repository.markRecallSent(recall.id)
                        val text = "Hello ${recall.patientName}, your ${recall.recallType} at FewClick Dental Clinic is due on ${recall.dueDate}. Please reply to book your preferred chair slot."
                        val uri = Uri.parse("https://api.whatsapp.com/send?phone=${recall.patientPhone.filter { it.isDigit() }}&text=${Uri.encode(text)}")
                        context.startActivity(Intent(Intent.ACTION_VIEW, uri))
                        Toast.makeText(context, "Recall sent to ${recall.patientName}!", Toast.LENGTH_SHORT).show()
                    }
                )
            }

            // 2. Practice Analytics
            item {
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    text = "Practice Analytics & Chair Utilization",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }

            item {
                MinimalCard {
                    Text(
                        text = "Chair Utilization Rate",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Chair 1 (General Operatory)", style = MaterialTheme.typography.bodySmall)
                        Text("84% Occupancy", fontWeight = FontWeight.Bold, color = DentalColors.StatusHealthy, style = MaterialTheme.typography.bodySmall)
                    }
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("Chair 2 (Aesthetic / Ortho Suite)", style = MaterialTheme.typography.bodySmall)
                        Text("91% Occupancy", fontWeight = FontWeight.Bold, color = DentalColors.StatusHealthy, style = MaterialTheme.typography.bodySmall)
                    }

                    Spacer(modifier = Modifier.height(12.dp))
                    Divider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
                    Spacer(modifier = Modifier.height(12.dp))

                    Text(
                        text = "Top Revenue Dental Procedures",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Spacer(modifier = Modifier.height(6.dp))
                    listOf(
                        "1. Clear Aligners / Ortho" to "₹3,80,000 (42%)",
                        "2. Titanium Implants" to "₹2,25,000 (25%)",
                        "3. Root Canal & Crowns" to "₹1,80,000 (20%)",
                        "4. Cosmetic Whitening & Scaling" to "₹1,15,000 (13%)"
                    ).forEach { (proc, rev) ->
                        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text(proc, style = MaterialTheme.typography.bodySmall)
                            Text(rev, fontWeight = FontWeight.Bold, style = MaterialTheme.typography.bodySmall, color = DentalColors.Teal700)
                        }
                        Spacer(modifier = Modifier.height(4.dp))
                    }
                }
            }

            // 3. Clinic Doctors & Settings
            item {
                MinimalCard {
                    Text(
                        text = "FewClick Dental Clinic Roster",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    listOf(
                        "Dr. Alex Rivera" to "Lead Endodontist & Implantologist",
                        "Dr. Sarah Chen" to "Specialist Orthodontist",
                        "Dr. Priya Nair" to "Cosmetic Dentist & Oral Surgeon"
                    ).forEach { (doc, spec) ->
                        Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(vertical = 3.dp)) {
                            Text("🩺", fontSize = 14.sp)
                            Spacer(modifier = Modifier.width(8.dp))
                            Column {
                                Text(doc, style = MaterialTheme.typography.labelMedium, fontWeight = FontWeight.Bold)
                                Text(spec, style = MaterialTheme.typography.bodySmall.copy(fontSize = 11.sp), color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(14.dp))
                    Divider(color = MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
                    Spacer(modifier = Modifier.height(14.dp))

                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text("Biometric Security", style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
                            Text("Fingerprint / Face ID lock active", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        Text("ACTIVE ✓", style = MaterialTheme.typography.labelSmall, color = DentalColors.StatusHealthy, fontWeight = FontWeight.Bold)
                    }

                    Spacer(modifier = Modifier.height(16.dp))

                    OutlinedButton(
                        onClick = onLogout,
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(10.dp),
                        colors = androidx.compose.material3.ButtonDefaults.outlinedButtonColors(contentColor = Color(0xFFEF4444))
                    ) {
                        Text("Sign Out of FewClick CRM", fontWeight = FontWeight.Bold)
                    }
                }
            }

            item { Spacer(modifier = Modifier.height(24.dp)) }
        }
    }
}

@Composable
fun DentalRecallItemCard(
    recall: DentalRecall,
    onSendWhatsApp: () -> Unit
) {
    val isPending = recall.status == "PENDING"

    MinimalCard {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = recall.patientName,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = recall.recallType,
                    style = MaterialTheme.typography.bodyMedium,
                    color = DentalColors.Teal700
                )
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = if (isPending) "Due: ${recall.dueDate}" else "Sent: ${recall.lastContacted}",
                    style = MaterialTheme.typography.labelSmall,
                    color = if (isPending) Color(0xFFD97706) else DentalColors.StatusHealthy,
                    fontWeight = FontWeight.Bold
                )
            }

            if (isPending) {
                Button(
                    onClick = onSendWhatsApp,
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Color(0xFF16A34A))
                ) {
                    Text("💬 1-Click WhatsApp", style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold))
                }
            } else {
                Box(
                    modifier = Modifier
                        .background(DentalColors.StatusHealthyBg, RoundedCornerShape(8.dp))
                        .padding(horizontal = 10.dp, vertical = 6.dp)
                ) {
                    Text(
                        text = "SENT ✓",
                        style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold),
                        color = DentalColors.StatusHealthy
                    )
                }
            }
        }
    }
}
