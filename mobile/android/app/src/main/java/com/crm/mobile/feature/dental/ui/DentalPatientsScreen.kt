package com.crm.mobile.feature.dental.ui

import android.content.Intent
import android.net.Uri
import android.widget.Toast
import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.Divider
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.crm.mobile.core.design.DentalColors
import com.crm.mobile.feature.dental.DentalPatient
import com.crm.mobile.feature.dental.DentalRepository
import com.crm.mobile.feature.dental.ToothCondition
import com.crm.mobile.feature.dental.ToothStatus
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DentalPatientsScreen(
    repository: DentalRepository,
    selectedPatientId: String? = null,
    onBack: (() -> Unit)? = null
) {
    val context = LocalContext.current
    val patients by repository.patients.collectAsState()
    val treatmentPlans by repository.treatmentPlans.collectAsState()

    var searchQuery by remember { mutableStateOf("") }
    var selectedFilter by remember { mutableStateOf("All") }
    var activePatientDetail by remember {
        mutableStateOf(patients.find { it.id == selectedPatientId } ?: patients.firstOrNull())
    }
    var selectedToothForEdit by remember { mutableStateOf<Pair<Int, ToothCondition?>?>(null) }

    val toothSheetState = rememberModalBottomSheetState()
    val scope = rememberCoroutineScope()

    val filteredPatients = patients.filter { p ->
        val matchesSearch = p.fullName.contains(searchQuery, ignoreCase = true) ||
                p.phone.contains(searchQuery) ||
                p.patientCode.contains(searchQuery, ignoreCase = true)
        val matchesFilter = when (selectedFilter) {
            "In-Treatment" -> p.ongoingTreatment != null
            "Medical Alerts" -> p.medicalAlerts.isNotEmpty()
            "Balances Due" -> p.outstandingBalance > 0
            else -> true
        }
        matchesSearch && matchesFilter
    }

    Scaffold(
        topBar = {
            Surface(
                color = MaterialTheme.colorScheme.surface,
                border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.5f))
            ) {
                Column(modifier = Modifier.padding(16.dp)) {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(
                                text = "🦷 Patients & Dental Records",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Text(
                                text = "${patients.size} active patient files with visual charts",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    OutlinedTextField(
                        value = searchQuery,
                        onValueChange = { searchQuery = it },
                        placeholder = { Text("Search by name, phone, #DEN code...") },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        singleLine = true
                    )

                    Spacer(modifier = Modifier.height(10.dp))

                    // Filter Chips
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        listOf("All", "In-Treatment", "Medical Alerts", "Balances Due").forEach { filter ->
                            val isSelected = selectedFilter == filter
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(if (isSelected) DentalColors.Teal600 else MaterialTheme.colorScheme.surfaceVariant)
                                    .clickable { selectedFilter = filter }
                                    .padding(horizontal = 12.dp, vertical = 6.dp)
                            ) {
                                Text(
                                    text = filter,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = if (isSelected) Color.White else MaterialTheme.colorScheme.onSurface,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                                )
                            }
                        }
                    }
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

            // If a patient is selected, show their full clinical odontogram record on top
            activePatientDetail?.let { activePatient ->
                item {
                    PatientDetailExpandedCard(
                        patient = activePatient,
                        treatmentPlans = treatmentPlans.filter { it.patientId == activePatient.id },
                        onToothClick = { toothNum, condition ->
                            selectedToothForEdit = Pair(toothNum, condition)
                        },
                        onToggleStep = { planId, stepNum ->
                            repository.toggleTreatmentStep(planId, stepNum)
                        },
                        onWhatsApp = {
                            val uri = Uri.parse("https://api.whatsapp.com/send?phone=${activePatient.phone.filter { it.isDigit() }}&text=Hello%20${Uri.encode(activePatient.fullName)},%20regarding%20your%20treatment%20at%20FewClick%20Dental%20Clinic...")
                            context.startActivity(Intent(Intent.ACTION_VIEW, uri))
                        },
                        onCall = {
                            val uri = Uri.parse("tel:${activePatient.phone}")
                            context.startActivity(Intent(Intent.ACTION_DIAL, uri))
                        }
                    )
                }
            }

            item {
                Text(
                    text = "Patient Directory (${filteredPatients.size})",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }

            items(filteredPatients) { patient ->
                PatientListItemCard(
                    patient = patient,
                    isSelected = activePatientDetail?.id == patient.id,
                    onClick = { activePatientDetail = patient },
                    formatCurrency = { repository.formatCurrency(it) }
                )
            }

            item { Spacer(modifier = Modifier.height(20.dp)) }
        }
    }

    // --- Tooth Charting Modal ---
    if (selectedToothForEdit != null && activePatientDetail != null) {
        val (toothNum, currentCondition) = selectedToothForEdit!!
        ModalBottomSheet(
            onDismissRequest = { selectedToothForEdit = null },
            sheetState = toothSheetState,
            containerColor = MaterialTheme.colorScheme.surface
        ) {
            ToothConditionEditSheet(
                toothNumber = toothNum,
                initialCondition = currentCondition,
                onSave = { status, notes ->
                    repository.updateToothCondition(activePatientDetail!!.id, toothNum, status, notes)
                    // Refresh active patient record
                    activePatientDetail = repository.patients.value.find { it.id == activePatientDetail!!.id }
                    scope.launch { toothSheetState.hide() }.invokeOnCompletion { selectedToothForEdit = null }
                    Toast.makeText(context, "Tooth #$toothNum marked as ${status.label}", Toast.LENGTH_SHORT).show()
                },
                onCancel = {
                    scope.launch { toothSheetState.hide() }.invokeOnCompletion { selectedToothForEdit = null }
                }
            )
        }
    }
}

@Composable
fun PatientDetailExpandedCard(
    patient: DentalPatient,
    treatmentPlans: List<com.crm.mobile.feature.dental.DentalTreatmentPlan>,
    onToothClick: (Int, ToothCondition?) -> Unit,
    onToggleStep: (String, Int) -> Unit,
    onWhatsApp: () -> Unit,
    onCall: () -> Unit
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(18.dp),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surface),
        border = CardDefaults.outlinedCardBorder().copy(brush = androidx.compose.ui.graphics.SolidColor(DentalColors.Teal600))
    ) {
        Column(modifier = Modifier.padding(16.dp)) {
            // Patient Header Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(46.dp)
                            .clip(CircleShape)
                            .background(DentalColors.Teal100),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = patient.fullName.take(2).uppercase(),
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = DentalColors.Teal900
                        )
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                text = patient.fullName,
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Spacer(modifier = Modifier.width(6.dp))
                            Box(
                                modifier = Modifier
                                    .background(MaterialTheme.colorScheme.surfaceVariant, RoundedCornerShape(4.dp))
                                    .padding(horizontal = 5.dp, vertical = 2.dp)
                            ) {
                                Text(
                                    text = patient.patientCode,
                                    style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
                                    fontWeight = FontWeight.Bold,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        }
                        Text(
                            text = "${patient.age} yrs • ${patient.gender} • Blood ${patient.bloodGroup}",
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant
                        )
                    }
                }

                // 1-Tap Contact Action Buttons
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(Color(0xFFDCFCE7))
                            .clickable(onClick = onWhatsApp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("💬", fontSize = 16.sp)
                    }
                    Box(
                        modifier = Modifier
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(Color(0xFFE0F2FE))
                            .clickable(onClick = onCall),
                        contentAlignment = Alignment.Center
                    ) {
                        Text("📞", fontSize = 16.sp)
                    }
                }
            }

            // Medical Alert Chips
            if (patient.medicalAlerts.isNotEmpty()) {
                Spacer(modifier = Modifier.height(10.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    patient.medicalAlerts.forEach { alert ->
                        MedicalAlertBadge(alert = alert)
                    }
                }
            }

            // Chief Complaint
            Spacer(modifier = Modifier.height(10.dp))
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.5f), RoundedCornerShape(8.dp))
                    .padding(8.dp)
            ) {
                Text(
                    text = "Chief Complaint: ${patient.chiefComplaint}",
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurface
                )
            }

            Spacer(modifier = Modifier.height(14.dp))

            // Visual Odontogram Component
            VisualOdontogramChart(
                teethMap = patient.teethConditions,
                onToothClick = onToothClick
            )

            // Ongoing Treatment Plan & Steps Checklist
            if (treatmentPlans.isNotEmpty()) {
                Spacer(modifier = Modifier.height(14.dp))
                Text(
                    text = "Active Clinical Treatment Plan",
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                    color = MaterialTheme.colorScheme.onSurface
                )
                Spacer(modifier = Modifier.height(8.dp))
                treatmentPlans.forEach { plan ->
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.4f), RoundedCornerShape(10.dp))
                            .padding(10.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                text = plan.procedureName,
                                style = MaterialTheme.typography.labelLarge,
                                fontWeight = FontWeight.Bold,
                                color = DentalColors.Teal700
                            )
                            Text(
                                text = "Teeth: ${plan.toothNumbers.joinToString()}",
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                        Spacer(modifier = Modifier.height(6.dp))
                        plan.steps.forEach { step ->
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .clickable { onToggleStep(plan.id, step.stepNumber) }
                                    .padding(vertical = 3.dp),
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = if (step.isCompleted) "☑" else "☐",
                                    color = if (step.isCompleted) DentalColors.StatusHealthy else MaterialTheme.colorScheme.onSurfaceVariant,
                                    fontSize = 16.sp,
                                    fontWeight = FontWeight.Bold
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = "Step ${step.stepNumber}: ${step.title}",
                                    style = MaterialTheme.typography.bodySmall,
                                    color = if (step.isCompleted) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun PatientListItemCard(
    patient: DentalPatient,
    isSelected: Boolean,
    onClick: () -> Unit,
    formatCurrency: (Double) -> String
) {
    MinimalCard(
        onClick = onClick,
        borderColor = if (isSelected) DentalColors.Teal600 else MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = patient.fullName,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(
                        text = patient.patientCode,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                }
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = patient.ongoingTreatment ?: "Routine Dental Care",
                    style = MaterialTheme.typography.bodySmall,
                    color = DentalColors.Teal700
                )
                if (patient.medicalAlerts.isNotEmpty()) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(
                        text = "⚠ ${patient.medicalAlerts.first()}",
                        style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
                        color = Color(0xFFE11D48),
                        fontWeight = FontWeight.Bold
                    )
                }
            }

            Column(horizontalAlignment = Alignment.End) {
                if (patient.outstandingBalance > 0) {
                    Text(
                        text = "Due: ${formatCurrency(patient.outstandingBalance)}",
                        style = MaterialTheme.typography.labelSmall.copy(fontWeight = FontWeight.Bold),
                        color = Color(0xFFEF4444)
                    )
                } else {
                    Text(
                        text = "Clear Balance",
                        style = MaterialTheme.typography.labelSmall,
                        color = DentalColors.StatusHealthy
                    )
                }
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = "Last: ${patient.lastVisit}",
                    style = MaterialTheme.typography.labelSmall.copy(fontSize = 9.sp),
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
            }
        }
    }
}

@Composable
fun ToothConditionEditSheet(
    toothNumber: Int,
    initialCondition: ToothCondition?,
    onSave: (status: ToothStatus, notes: String) -> Unit,
    onCancel: () -> Unit
) {
    var selectedStatus by remember { mutableStateOf(initialCondition?.getToothStatus() ?: ToothStatus.HEALTHY) }
    var notes by remember { mutableStateOf(initialCondition?.notes ?: "") }

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 20.dp)
            .padding(bottom = 32.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp)
    ) {
        Text(
            text = "🦷 Chart Tooth #$toothNumber",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.Bold,
            color = MaterialTheme.colorScheme.onSurface
        )

        Text(
            text = "Select Condition / Clinical Finding:",
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant
        )

        // Status Grid
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .horizontalScroll(rememberScrollState()),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            ToothStatus.values().forEach { status ->
                val isSelected = selectedStatus == status
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(if (isSelected) status.color else status.bgColor)
                        .clickable { selectedStatus = status }
                        .padding(horizontal = 12.dp, vertical = 8.dp)
                ) {
                    Text(
                        text = status.label,
                        style = MaterialTheme.typography.labelSmall,
                        color = if (isSelected) Color.White else status.color,
                        fontWeight = FontWeight.Bold
                    )
                }
            }
        }

        OutlinedTextField(
            value = notes,
            onValueChange = { notes = it },
            label = { Text("Clinical Note / Material / Surface (e.g. MO Cavity, Zirconia)") },
            modifier = Modifier.fillMaxWidth(),
            shape = RoundedCornerShape(12.dp)
        )

        Button(
            onClick = { onSave(selectedStatus, notes) },
            shape = RoundedCornerShape(12.dp),
            colors = ButtonDefaults.buttonColors(containerColor = DentalColors.Teal600),
            modifier = Modifier.fillMaxWidth()
        ) {
            Text("Update Tooth #$toothNumber Chart", style = MaterialTheme.typography.labelLarge)
        }
    }
}
