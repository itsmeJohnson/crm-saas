package com.crm.mobile.feature.dental.ui

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.crm.mobile.core.design.DentalColors
import com.crm.mobile.feature.dental.DentalAppointment
import com.crm.mobile.feature.dental.DentalRepository
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DentalDashboardScreen(
    repository: DentalRepository,
    onNavigateToPatients: () -> Unit,
    onNavigateToAppointments: () -> Unit,
    onNavigateToBilling: () -> Unit,
    onNavigateToRecalls: () -> Unit,
    onOpenPatientProfile: (String) -> Unit
) {
    val context = LocalContext.current
    val stats by repository.stats.collectAsState()
    val appointments by repository.appointments.collectAsState()
    val patients by repository.patients.collectAsState()
    val recalls by repository.recalls.collectAsState()

    var showQuickBookSheet by remember { mutableStateOf(false) }
    var showNewPatientSheet by remember { mutableStateOf(false) }
    var showPaymentSheet by remember { mutableStateOf(false) }

    val sheetState = rememberModalBottomSheetState()
    val scope = rememberCoroutineScope()

    Scaffold(
        topBar = {
            DentalClinicHeader(
                clinicName = "FewClick Dental Clinic",
                activeDoctor = "Dr. Alex Rivera (Endodontist)",
                dateString = "Sunday, Aug 9, 2026",
                onNotificationClick = {
                    Toast.makeText(context, "6 Patient Recalls Due This Week", Toast.LENGTH_SHORT).show()
                }
            )
        },
        containerColor = MaterialTheme.colorScheme.background
    ) { padding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // 1. Key Clinic Metric Cards
            item {
                Spacer(modifier = Modifier.height(4.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    DentalMetricPill(
                        title = "Today's Queue",
                        value = "${stats.todayAppointmentsCount} Patients",
                        badgeText = "${stats.inChairCount} In-Chair",
                        accentColor = DentalColors.Teal600,
                        modifier = Modifier.weight(1f)
                    )
                    DentalMetricPill(
                        title = "Today's Collections",
                        value = repository.formatCurrency(stats.todayCollections),
                        badgeText = "+18%",
                        accentColor = DentalColors.StatusHealthy,
                        modifier = Modifier.weight(1f)
                    )
                }
                Spacer(modifier = Modifier.height(10.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    DentalMetricPill(
                        title = "Active Treatments",
                        value = "${stats.pendingTreatmentsCount} Cases",
                        badgeText = "Ortho / RCT",
                        accentColor = Color(0xFF0284C7),
                        modifier = Modifier.weight(1f)
                    )
                    DentalMetricPill(
                        title = "Recalls Due",
                        value = "${stats.dueRecallsCount} Due",
                        badgeText = "WhatsApp Ready",
                        accentColor = Color(0xFFF59E0B),
                        modifier = Modifier.weight(1f)
                    )
                }
            }

            // 2. "FewClick" Rapid Action Ribbon
            item {
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(16.dp),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
                    border = CardDefaults.outlinedCardBorder().copy(
                        brush = androidx.compose.ui.graphics.SolidColor(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f))
                    )
                ) {
                    Column(modifier = Modifier.padding(14.dp)) {
                        Text(
                            text = "⚡ FewClick Rapid Actions",
                            style = MaterialTheme.typography.labelSmall.copy(letterSpacing = 0.5.sp),
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            fontWeight = FontWeight.Bold
                        )
                        Spacer(modifier = Modifier.height(10.dp))
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            QuickActionCircle(
                                iconText = "📅",
                                label = "Quick Book",
                                onClick = { showQuickBookSheet = true },
                                accentColor = DentalColors.Teal600
                            )
                            QuickActionCircle(
                                iconText = "👤",
                                label = "New Patient",
                                onClick = { showNewPatientSheet = true },
                                accentColor = Color(0xFF0284C7)
                            )
                            QuickActionCircle(
                                iconText = "🦷",
                                label = "Odontogram",
                                onClick = onNavigateToPatients,
                                accentColor = Color(0xFF8B5CF6)
                            )
                            QuickActionCircle(
                                iconText = "💳",
                                label = "Collect Pay",
                                onClick = { showPaymentSheet = true },
                                accentColor = DentalColors.StatusHealthy
                            )
                            QuickActionCircle(
                                iconText = "💬",
                                label = "Recalls",
                                onClick = onNavigateToRecalls,
                                accentColor = Color(0xFFF59E0B)
                            )
                        }
                    }
                }
            }

            // 3. Live Chair Queue Header
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Column {
                        Text(
                            text = "Today's Patient Queue",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = MaterialTheme.colorScheme.onSurface
                        )
                        Text(
                            text = "${appointments.size} appointments scheduled today",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                    Text(
                        text = "View Schedule →",
                        style = MaterialTheme.typography.labelSmall,
                        color = DentalColors.Teal600,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.clickable(onClick = onNavigateToAppointments)
                    )
                }
            }

            // 4. Live Appointments List
            items(appointments) { appt ->
                DashboardAppointmentCard(
                    appointment = appt,
                    onAdvanceStatus = { repository.advanceAppointmentStatus(appt.id) },
                    onOpenProfile = { onOpenPatientProfile(appt.patientId) },
                    onWhatsApp = {
                        val uri = Uri.parse("https://api.whatsapp.com/send?phone=${appt.patientPhone.filter { it.isDigit() }}&text=Hello%20${Uri.encode(appt.patientName)},%20this%20is%20a%20reminder%20for%20your%20appointment%20at%20FewClick%20Dental%20Clinic%20today%20at%20${Uri.encode(appt.timeSlot)}.")
                        context.startActivity(Intent(Intent.ACTION_VIEW, uri))
                    }
                )
            }

            // 5. Urgent Recalls Alert Card
            if (recalls.isNotEmpty()) {
                item {
                    MinimalCard(
                        onClick = onNavigateToRecalls,
                        containerColor = DentalColors.Teal50,
                        borderColor = DentalColors.Teal200
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Box(
                                    modifier = Modifier
                                        .size(36.dp)
                                        .background(DentalColors.Teal100, CircleShape),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Text("🔔", fontSize = 16.sp)
                                }
                                Spacer(modifier = Modifier.width(12.dp))
                                Column {
                                    Text(
                                        text = "${recalls.count { it.status == "PENDING" }} Recalls Due for Contact",
                                        style = MaterialTheme.typography.titleSmall,
                                        fontWeight = FontWeight.Bold,
                                        color = DentalColors.Teal900
                                    )
                                    Text(
                                        text = "Hygiene & Orthodontic follow-ups",
                                        style = MaterialTheme.typography.bodySmall,
                                        color = DentalColors.Teal700
                                    )
                                }
                            }
                            Text(
                                text = "Send 1-Click →",
                                style = MaterialTheme.typography.labelSmall,
                                color = DentalColors.Teal600,
                                fontWeight = FontWeight.Bold
                            )
                        }
                    }
                    Spacer(modifier = Modifier.height(16.dp))
                }
            }
        }
    }

    // --- Bottom Sheets for Fast Workflows ---

    if (showQuickBookSheet) {
        ModalBottomSheet(
            onDismissRequest = { showQuickBookSheet = false },
            sheetState = sheetState,
            containerColor = MaterialTheme.colorScheme.surface
        ) {
            QuickBookBottomSheetContent(
                catalog = repository.procedureCatalog,
                onBook = { name, phone, procedure, chair, timeSlot, doctor ->
                    repository.quickBookAppointment(name, phone, procedure, chair, timeSlot, doctor)
                    scope.launch { sheetState.hide() }.invokeOnCompletion { showQuickBookSheet = false }
                    Toast.makeText(context, "Appointment Booked in 1 Click!", Toast.LENGTH_SHORT).show()
                },
                onCancel = {
                    scope.launch { sheetState.hide() }.invokeOnCompletion { showQuickBookSheet = false }
                }
            )
        }
    }

    if (showNewPatientSheet) {
        ModalBottomSheet(
            onDismissRequest = { showNewPatientSheet = false },
            sheetState = sheetState,
            containerColor = MaterialTheme.colorScheme.surface
        ) {
            NewPatientBottomSheetContent(
                onRegister = { name, phone, age, gender, complaint, alerts ->
                    val p = repository.registerNewPatient(name, phone, age, gender, complaint, alerts)
                    scope.launch { sheetState.hide() }.invokeOnCompletion {
                        showNewPatientSheet = false
                        onOpenPatientProfile(p.id)
                    }
                    Toast.makeText(context, "Patient ${p.patientCode} Registered!", Toast.LENGTH_SHORT).show()
                },
                onCancel = {
                    scope.launch { sheetState.hide() }.invokeOnCompletion { showNewPatientSheet = false }
                }
            )
        }
    }

    if (showPaymentSheet) {
        ModalBottomSheet(
            onDismissRequest = { showPaymentSheet = false },
            sheetState = sheetState,
            containerColor = MaterialTheme.colorScheme.surface
        ) {
            QuickPaymentBottomSheetContent(
                patients = patients,
                onRecord = { patientName, amount, method, notes ->
                    repository.recordPayment(patientName, amount, method, notes)
                    scope.launch { sheetState.hide() }.invokeOnCompletion { showPaymentSheet = false }
                    Toast.makeText(context, "Payment of ₹${amount.toInt()} Recorded!", Toast.LENGTH_SHORT).show()
                },
                onCancel = {
                    scope.launch { sheetState.hide() }.invokeOnCompletion { showPaymentSheet = false }
                }
            )
        }
    }
}

@Composable
fun DentalClinicHeader(
    clinicName: String,
    activeDoctor: String,
    dateString: String,
    onNotificationClick: () -> Unit
) {
    Surface(
        color = MaterialTheme.colorScheme.surface,
        border = androidx.compose.foundation.BorderStroke(
            1.dp,
            MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f)
        )
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(40.dp)
                        .clip(RoundedCornerShape(10.dp))
                        .background(DentalColors.Teal600),
                    contentAlignment = Alignment.Center
                ) {
                    Text("🦷", fontSize = 20.sp)
                }
                Spacer(modifier = Modifier.width(10.dp))
                Column {
                    Text(
                        text = clinicName,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Text(
                        text = "$activeDoctor • $dateString",
                        style = MaterialTheme.typography.bodySmall.copy(fontSize = 11.sp),
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
            }
            Box(
                modifier = Modifier
                    .size(36.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .clickable(onClick = onNotificationClick),
                contentAlignment = Alignment.Center
            ) {
                Text("🔔", fontSize = 16.sp)
            }
        }
    }
}

@Composable
fun DashboardAppointmentCard(
    appointment: DentalAppointment,
    onAdvanceStatus: () -> Unit,
    onOpenProfile: () -> Unit,
    onWhatsApp: () -> Unit
) {
    val status = appointment.getApptStatus()

    MinimalCard(
        onClick = onOpenProfile,
        borderColor = if (status == com.crm.mobile.feature.dental.AppointmentStatus.IN_CHAIR) DentalColors.Teal500 else MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.Top
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = appointment.timeSlot,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.Bold,
                        color = DentalColors.Teal600
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "• ${appointment.chair}",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = appointment.patientName,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = appointment.procedure,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }

            DentalStatusBadge(status = status)
        }

        Spacer(modifier = Modifier.height(12.dp))

        // Action Buttons Row
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Next Workflow Step Button
            if (status != com.crm.mobile.feature.dental.AppointmentStatus.COMPLETED) {
                Button(
                    onClick = onAdvanceStatus,
                    shape = RoundedCornerShape(10.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = if (status == com.crm.mobile.feature.dental.AppointmentStatus.IN_CHAIR) DentalColors.StatusHealthy else DentalColors.Teal600
                    ),
                    modifier = Modifier.weight(1f)
                ) {
                    Text(
                        text = when (status) {
                            com.crm.mobile.feature.dental.AppointmentStatus.SCHEDULED -> "Check-In Patient"
                            com.crm.mobile.feature.dental.AppointmentStatus.WAITING -> "Take to Chair 🦷"
                            com.crm.mobile.feature.dental.AppointmentStatus.IN_CHAIR -> "Complete Visit ✓"
                            else -> "Update"
                        },
                        style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold)
                    )
                }
            } else {
                OutlinedButton(
                    onClick = onOpenProfile,
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier.weight(1f)
                ) {
                    Text("View Dental Record", style = MaterialTheme.typography.labelSmall)
                }
            }

            // 1-Tap WhatsApp Reminder
            OutlinedButton(
                onClick = onWhatsApp,
                shape = RoundedCornerShape(10.dp),
                border = androidx.compose.foundation.BorderStroke(1.dp, Color(0xFF25D366))
            ) {
                Text("💬 WhatsApp", color = Color(0xFF16A34A), style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold))
            }
        }
    }
}

// ---------------------------------------------------------------------------
// Bottom Sheet Contents
// ---------------------------------------------------------------------------

@Composable
fun QuickBookBottomSheetContent(
    catalog: List<com.crm.mobile.feature.dental.DentalProcedureCatalogItem>,
    onBook: (name: String, phone: String, procedure: String, chair: String, timeSlot: String, doctor: String) -> Unit,
    onCancel: () -> Unit
) {
    var name by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("+91 ") }
    var selectedProcedure by remember { mutableStateOf(catalog.firstOrNull()?.name ?: "Root Canal Therapy (RCT)") }
    var selectedChair by remember { mutableStateOf("Chair 1 (Operatory)") }
    var timeSlot by remember { mutableStateOf("11:00 AM") }
    var selectedDoctor by remember { mutableStateOf("Dr. Alex Rivera") }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .padding(bottom = 32.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text(
            text = "⚡ Quick Book Dental Appointment",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface
        )

        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            label = { Text("Patient Full Name") },
            placeholder = { Text("e.g. Ramesh Kumar") },
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            singleLine = true
        )

        OutlinedTextField(
            value = phone,
            onValueChange = { phone = it },
            label = { Text("Phone Number") },
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
            singleLine = true
        )

        Text(
            text = "Select Procedure",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            catalog.take(5).forEach { item ->
                val isSelected = selectedProcedure == item.name
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (isSelected) DentalColors.Teal600 else MaterialTheme.colorScheme.surfaceVariant)
                        .clickable { selectedProcedure = item.name }
                        .padding(horizontal = 12.dp, vertical = 8.dp)
                ) {
                    Text(
                        text = item.name,
                        style = MaterialTheme.typography.labelSmall,
                        color = if (isSelected) Color.White else MaterialTheme.colorScheme.onSurface,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                    )
                }
            }
        }

        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            OutlinedTextField(
                value = timeSlot,
                onValueChange = { timeSlot = it },
                label = { Text("Time Slot") },
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(12.dp),
                singleLine = true
            )
            OutlinedTextField(
                value = selectedChair,
                onValueChange = { selectedChair = it },
                label = { Text("Operatory Chair") },
                modifier = Modifier.weight(1f),
                shape = RoundedCornerShape(12.dp),
                singleLine = true
            )
        }

        Button(
            onClick = {
                if (name.isNotBlank()) {
                    onBook(name, phone, selectedProcedure, selectedChair, timeSlot, selectedDoctor)
                }
            },
            enabled = name.isNotBlank(),
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.buttonColors(containerColor = DentalColors.Teal600),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Confirm 1-Click Booking", style = MaterialTheme.typography.labelLarge)
        }
    }
}

@Composable
fun NewPatientBottomSheetContent(
    onRegister: (name: String, phone: String, age: Int, gender: String, complaint: String, alerts: List<String>) -> Unit,
    onCancel: () -> Unit
) {
    var name by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("+91 ") }
    var ageStr by remember { mutableStateOf("30") }
    var gender by remember { mutableStateOf("Female") }
    var complaint by remember { mutableStateOf("") }
    var selectedAlerts by remember { mutableStateOf(setOf<String>()) }

    val commonAlerts = listOf("Penicillin Allergy", "Diabetic", "Hypertensive", "Bleeding Disorder", "Pregnant")

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .padding(bottom = 32.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text(
            text = "➕ Register Dental Patient",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface
        )

        OutlinedTextField(
            value = name,
            onValueChange = { name = it },
            label = { Text("Patient Full Name") },
            placeholder = { Text("e.g. Meera Nair") },
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            singleLine = true
        )

        Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            OutlinedTextField(
                value = phone,
                onValueChange = { phone = it },
                label = { Text("Phone") },
                modifier = Modifier.weight(1.3f),
                shape = RoundedCornerShape(12.dp),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                singleLine = true
            )
            OutlinedTextField(
                value = ageStr,
                onValueChange = { ageStr = it },
                label = { Text("Age") },
                modifier = Modifier.weight(0.7f),
                shape = RoundedCornerShape(12.dp),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                singleLine = true
            )
        }

        OutlinedTextField(
            value = complaint,
            onValueChange = { complaint = it },
            label = { Text("Chief Dental Complaint") },
            placeholder = { Text("e.g. Tooth sensitivity / Aligners") },
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp)
        )

        Text(
            text = "Medical History Alerts (Tap to toggle):",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            commonAlerts.forEach { alert ->
                val isSelected = selectedAlerts.contains(alert)
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (isSelected) Color(0xFFFDA4AF) else MaterialTheme.colorScheme.surfaceVariant)
                        .clickable {
                            selectedAlerts = if (isSelected) selectedAlerts - alert else selectedAlerts + alert
                        }
                        .padding(horizontal = 10.dp, vertical = 6.dp)
                ) {
                    Text(
                        text = if (isSelected) "⚠ $alert" else alert,
                        style = MaterialTheme.typography.labelSmall,
                        color = if (isSelected) Color(0xFF881337) else MaterialTheme.colorScheme.onSurface,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                    )
                }
            }
        }

        Button(
            onClick = {
                if (name.isNotBlank()) {
                    onRegister(
                        name,
                        phone,
                        ageStr.toIntOrNull() ?: 25,
                        gender,
                        complaint.ifBlank { "Routine Checkup" },
                        selectedAlerts.toList()
                    )
                }
            },
            enabled = name.isNotBlank(),
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.buttonColors(containerColor = DentalColors.Teal600),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Create Patient & Open Chart", style = MaterialTheme.typography.labelLarge)
        }
    }
}

@Composable
fun QuickPaymentBottomSheetContent(
    patients: List<com.crm.mobile.feature.dental.DentalPatient>,
    onRecord: (patientName: String, amount: Double, method: String, notes: String) -> Unit,
    onCancel: () -> Unit
) {
    var selectedPatientName by remember { mutableStateOf(patients.firstOrNull()?.fullName ?: "Aarav Sharma") }
    var amountStr by remember { mutableStateOf("5000") }
    var method by remember { mutableStateOf("UPI (GPay / PhonePe)") }
    var notes by remember { mutableStateOf("Treatment payment") }

    val paymentMethods = listOf("UPI (GPay / PhonePe)", "Credit / Debit Card", "Cash", "Dental Insurance")

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .padding(bottom = 32.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text(
            text = "💳 Record Dental Payment",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface
        )

        OutlinedTextField(
            value = selectedPatientName,
            onValueChange = { selectedPatientName = it },
            label = { Text("Patient Name") },
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            singleLine = true
        )

        OutlinedTextField(
            value = amountStr,
            onValueChange = { amountStr = it },
            label = { Text("Amount (₹ INR)") },
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
            singleLine = true
        )

        Text(
            text = "Payment Method",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            paymentMethods.forEach { m ->
                val isSelected = method == m
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (isSelected) DentalColors.StatusHealthy else MaterialTheme.colorScheme.surfaceVariant)
                        .clickable { method = m }
                        .padding(horizontal = 12.dp, vertical = 8.dp)
                ) {
                    Text(
                        text = m,
                        style = MaterialTheme.typography.labelSmall,
                        color = if (isSelected) Color.White else MaterialTheme.colorScheme.onSurface,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                    )
                }
            }
        }

        OutlinedTextField(
            value = notes,
            onValueChange = { notes = it },
            label = { Text("Procedure / Receipt Note") },
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp)
        )

        Button(
            onClick = {
                val amt = amountStr.toDoubleOrNull() ?: 0.0
                if (amt > 0) {
                    onRecord(selectedPatientName, amt, method, notes)
                }
            },
            enabled = (amountStr.toDoubleOrNull() ?: 0.0) > 0,
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.buttonColors(containerColor = DentalColors.StatusHealthy),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Record Payment & Send Receipt", style = MaterialTheme.typography.labelLarge)
        }
    }
}
