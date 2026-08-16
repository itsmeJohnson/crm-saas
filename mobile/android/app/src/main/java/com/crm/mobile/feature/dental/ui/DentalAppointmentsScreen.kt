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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
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
import com.crm.mobile.feature.dental.DentalAppointment
import com.crm.mobile.feature.dental.DentalRepository
import kotlinx.coroutines.launch

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DentalAppointmentsScreen(
    repository: DentalRepository,
    onOpenPatientProfile: (String) -> Unit
) {
    val context = LocalContext.current
    val appointments by repository.appointments.collectAsState()
    val scope = rememberCoroutineScope()
    val bookSheetState = rememberModalBottomSheetState()

    var selectedChairFilter by remember { mutableStateOf("All Chairs") }
    var selectedStatusFilter by remember { mutableStateOf("All") }
    var showBookSheet by remember { mutableStateOf(false) }

    val filteredAppointments = appointments.filter { appt ->
        val matchesChair = when (selectedChairFilter) {
            "Chair 1" -> appt.chair.contains("Chair 1")
            "Chair 2" -> appt.chair.contains("Chair 2")
            else -> true
        }
        val matchesStatus = when (selectedStatusFilter) {
            "In Chair" -> appt.status == "IN_CHAIR"
            "Waiting" -> appt.status == "WAITING"
            "Scheduled" -> appt.status == "SCHEDULED"
            "Completed" -> appt.status == "COMPLETED"
            else -> true
        }
        matchesChair && matchesStatus
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
                                text = "📅 Chair Schedules & Appointments",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Bold,
                                color = MaterialTheme.colorScheme.onSurface
                            )
                            Text(
                                text = "Operatory Chair 1 & Aesthetic Suite 2",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant
                            )
                        }
                    }

                    Spacer(modifier = Modifier.height(12.dp))

                    // Chair Selector Chips
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        listOf("All Chairs", "Chair 1", "Chair 2").forEach { chair ->
                            val isSelected = selectedChairFilter == chair
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(if (isSelected) DentalColors.Teal600 else MaterialTheme.colorScheme.surfaceVariant)
                                    .clickable { selectedChairFilter = chair }
                                    .padding(horizontal = 14.dp, vertical = 6.dp)
                            ) {
                                Text(
                                    text = chair,
                                    style = MaterialTheme.typography.labelSmall,
                                    color = if (isSelected) Color.White else MaterialTheme.colorScheme.onSurface,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                                )
                            }
                        }
                    }

                    Spacer(modifier = Modifier.height(8.dp))

                    // Status Filters
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .horizontalScroll(rememberScrollState()),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        listOf("All", "In Chair", "Waiting", "Scheduled", "Completed").forEach { st ->
                            val isSelected = selectedStatusFilter == st
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(if (isSelected) MaterialTheme.colorScheme.primaryContainer else Color.Transparent)
                                    .clickable { selectedStatusFilter = st }
                                    .padding(horizontal = 10.dp, vertical = 4.dp)
                            ) {
                                Text(
                                    text = st,
                                    style = MaterialTheme.typography.labelSmall.copy(fontSize = 11.sp),
                                    color = if (isSelected) MaterialTheme.colorScheme.onPrimaryContainer else MaterialTheme.colorScheme.onSurfaceVariant,
                                    fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal
                                )
                            }
                        }
                    }
                }
            }
        },
        floatingActionButton = {
            FloatingActionButton(
                onClick = { showBookSheet = true },
                containerColor = DentalColors.Teal600,
                contentColor = Color.White,
                shape = RoundedCornerShape(16.dp)
            ) {
                Row(modifier = Modifier.padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
                    Text("+ Quick Book Slot", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelLarge)
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

            if (filteredAppointments.isEmpty()) {
                item {
                    MinimalCard {
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(vertical = 24.dp),
                            horizontalAlignment = Alignment.CenterHorizontally
                        ) {
                            Text("No appointments found for this filter", style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }

            items(filteredAppointments) { appt ->
                DashboardAppointmentCard(
                    appointment = appt,
                    onAdvanceStatus = { repository.advanceAppointmentStatus(appt.id) },
                    onOpenProfile = { onOpenPatientProfile(appt.patientId) },
                    onWhatsApp = {
                        val uri = Uri.parse("https://api.whatsapp.com/send?phone=${appt.patientPhone.filter { it.isDigit() }}&text=Hello%20${Uri.encode(appt.patientName)},%20confirming%20your%20dental%20appointment%20at%20FewClick%20Dental%20Clinic%20on%20${Uri.encode(appt.timeSlot)}.")
                        context.startActivity(Intent(Intent.ACTION_VIEW, uri))
                    }
                )
            }

            item { Spacer(modifier = Modifier.height(80.dp)) }
        }
    }

    if (showBookSheet) {
        ModalBottomSheet(
            onDismissRequest = { showBookSheet = false },
            sheetState = bookSheetState,
            containerColor = MaterialTheme.colorScheme.surface
        ) {
            QuickBookBottomSheetContent(
                catalog = repository.procedureCatalog,
                onBook = { name, phone, procedure, chair, timeSlot, doctor ->
                    repository.quickBookAppointment(name, phone, procedure, chair, timeSlot, doctor)
                    scope.launch { bookSheetState.hide() }.invokeOnCompletion { showBookSheet = false }
                    Toast.makeText(context, "Slot booked for $name!", Toast.LENGTH_SHORT).show()
                },
                onCancel = {
                    scope.launch { bookSheetState.hide() }.invokeOnCompletion { showBookSheet = false }
                }
            )
        }
    }
}
