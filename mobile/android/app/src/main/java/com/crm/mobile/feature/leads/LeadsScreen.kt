package com.crm.mobile.feature.leads

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.crm.mobile.core.design.DentalColors
import com.crm.mobile.core.util.PhoneActions
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.combine
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import javax.inject.Inject

@HiltViewModel
class LeadsViewModel @Inject constructor(
    private val repo: LeadRepository,
) : ViewModel() {

    private val _query = MutableStateFlow("")
    val query: StateFlow<String> = _query.asStateFlow()

    private val _statusFilter = MutableStateFlow<String?>(null)
    val statusFilter: StateFlow<String?> = _statusFilter.asStateFlow()

    private val _loading = MutableStateFlow(true)
    val loading: StateFlow<Boolean> = _loading.asStateFlow()

    private val _offline = MutableStateFlow(false)
    val offline: StateFlow<Boolean> = _offline.asStateFlow()

    val leads: StateFlow<List<Lead>> =
        combine(repo.leads, _query, _statusFilter) { list, q, filter ->
            list.filter { lead ->
                val matchesQuery = q.isBlank() ||
                        lead.title.contains(q, ignoreCase = true) ||
                        lead.name.contains(q, ignoreCase = true) ||
                        (lead.phone != null && lead.phone.contains(q))
                val matchesStatus = when {
                    filter == null || filter.equals("All", ignoreCase = true) -> true
                    filter.equals("Processed", ignoreCase = true) ->
                        lead.status.contains("Processed", ignoreCase = true) ||
                        lead.status.contains("Proposal", ignoreCase = true) ||
                        lead.status.contains("Negotiation", ignoreCase = true) ||
                        lead.status.contains("In Progress", ignoreCase = true)
                    else ->
                        lead.status.contains(filter, ignoreCase = true) ||
                        filter.contains(lead.status, ignoreCase = true)
                }
                matchesQuery && matchesStatus
            }
        }.stateIn(viewModelScope, SharingStarted.WhileSubscribed(5_000), emptyList())

    init { refresh() }

    fun setQuery(q: String) { _query.value = q }
    fun setStatusFilter(status: String?) {
        _statusFilter.value = if (_statusFilter.value == status) null else status
    }

    fun updateLeadStatus(id: String, newStatus: String) {
        viewModelScope.launch {
            repo.updateStatus(id, newStatus)
        }
    }

    fun createLead(
        name: String,
        title: String,
        phone: String?,
        priority: String,
        value: Double,
        onDone: () -> Unit
    ) {
        viewModelScope.launch {
            repo.createLead(name, title, phone, priority, value)
            onDone()
        }
    }

    fun refresh() {
        _loading.value = true
        viewModelScope.launch {
            _offline.value = !repo.refresh()
            _loading.value = false
        }
    }
}

// Complete list of pipeline stages horizontally scrollable
private val STATUS_PRESETS = listOf("New", "Contacted", "Qualified", "Proposal", "Processed", "Won", "Lost")

@Composable
fun LeadsScreen(
    onOpenCockpit: (String?) -> Unit = {},
    onCompose: (String) -> Unit = {},
    vm: LeadsViewModel = hiltViewModel(),
) {
    val context = LocalContext.current
    val leads by vm.leads.collectAsStateWithLifecycle()
    val query by vm.query.collectAsStateWithLifecycle()
    val statusFilter by vm.statusFilter.collectAsStateWithLifecycle()
    val loading by vm.loading.collectAsStateWithLifecycle()
    val offline by vm.offline.collectAsStateWithLifecycle()

    var showCreateLeadDialog by remember { mutableStateOf(false) }
    var selectedLeadForStageChange by remember { mutableStateOf<Lead?>(null) }

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(
                onClick = { showCreateLeadDialog = true },
                containerColor = DentalColors.Teal600,
                contentColor = Color.White,
                shape = RoundedCornerShape(16.dp)
            ) {
                Row(
                    modifier = Modifier.padding(horizontal = 16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    Text("🎯", fontSize = 18.sp)
                    Text("+ Add Lead", fontWeight = FontWeight.Bold)
                }
            }
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 14.dp)
        ) {
            if (offline) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(vertical = 6.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        "⚠️ Offline — showing cached leads",
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.error,
                    )
                    Text(
                        "Retry ↺",
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.primary,
                        modifier = Modifier.clickable { vm.refresh() }
                    )
                }
            }

            OutlinedTextField(
                value = query,
                onValueChange = vm::setQuery,
                label = { Text("Search leads by name, title, or phone") },
                trailingIcon = {
                    IconButton(onClick = vm::refresh) {
                        Text("🔄", fontSize = 16.sp)
                    }
                },
                singleLine = true,
                shape = RoundedCornerShape(12.dp),
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            )

            // UX-Friendly Horizontally Scrollable Filter Chips Row
            LazyRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(vertical = 10.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                item {
                    FilterChip(
                        selected = statusFilter == null,
                        onClick = { vm.setStatusFilter(null) },
                        label = { Text("All (${leads.size})", fontWeight = if (statusFilter == null) FontWeight.Bold else FontWeight.Normal) },
                    )
                }
                items(STATUS_PRESETS) { status ->
                    val isSelected = statusFilter?.equals(status, ignoreCase = true) == true
                    FilterChip(
                        selected = isSelected,
                        onClick = { vm.setStatusFilter(status) },
                        label = { Text(status, fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal) },
                    )
                }
            }

            when {
                loading && leads.isEmpty() ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
                leads.isEmpty() ->
                    Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                            Text("No leads found for selected filter", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Button(
                                onClick = { showCreateLeadDialog = true },
                                colors = ButtonDefaults.buttonColors(containerColor = DentalColors.Teal600),
                                shape = RoundedCornerShape(10.dp)
                            ) {
                                Text("+ Create New Lead", fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                else -> LazyColumn(
                    verticalArrangement = Arrangement.spacedBy(10.dp),
                    modifier = Modifier.fillMaxSize(),
                ) {
                    items(leads, key = { it.id }) { lead ->
                        LeadRow(
                            lead = lead,
                            onStatusClick = { selectedLeadForStageChange = lead },
                            onCockpitClick = { onOpenCockpit(lead.id) },
                            onComposeClick = { onCompose(lead.id) },
                            onCallClick = { PhoneActions.launchDialer(context, lead.phone) },
                            onWhatsAppClick = {
                                PhoneActions.launchWhatsApp(
                                    context,
                                    lead.phone,
                                    "Hello ${lead.name}, this is regarding your inquiry about ${lead.title}."
                                )
                            }
                        )
                    }
                    item { Box(Modifier.padding(bottom = 60.dp)) {} }
                }
            }
        }
    }

    // Quick Stage Transition Dialog
    selectedLeadForStageChange?.let { targetLead ->
        AlertDialog(
            onDismissRequest = { selectedLeadForStageChange = null },
            title = { Text("Update Pipeline Stage", fontWeight = FontWeight.Bold) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text(
                        "Move ${targetLead.name} to next stage:",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    STATUS_PRESETS.forEach { st ->
                        val isCurrent = targetLead.status.equals(st, ignoreCase = true)
                        Card(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clickable {
                                    vm.updateLeadStatus(targetLead.id, st)
                                    selectedLeadForStageChange = null
                                },
                            shape = RoundedCornerShape(10.dp),
                            colors = CardDefaults.cardColors(
                                containerColor = if (isCurrent) DentalColors.Teal50 else MaterialTheme.colorScheme.surface
                            ),
                            border = CardDefaults.outlinedCardBorder()
                        ) {
                            Row(
                                modifier = Modifier.padding(horizontal = 14.dp, vertical = 10.dp),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(st, fontWeight = if (isCurrent) FontWeight.Bold else FontWeight.Medium)
                                if (isCurrent) Text("✓ Current", style = MaterialTheme.typography.labelSmall, color = DentalColors.Teal700, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            },
            confirmButton = {
                OutlinedButton(onClick = { selectedLeadForStageChange = null }) {
                    Text("Cancel")
                }
            }
        )
    }

    // Add Lead Dialog
    if (showCreateLeadDialog) {
        CreateLeadDialog(
            onDismiss = { showCreateLeadDialog = false },
            onSave = { name, title, phone, priority, value ->
                vm.createLead(name, title, phone, priority, value) {
                    showCreateLeadDialog = false
                }
            }
        )
    }
}

@Composable
private fun CreateLeadDialog(
    onDismiss: () -> Unit,
    onSave: (name: String, title: String, phone: String?, priority: String, value: Double) -> Unit
) {
    var name by remember { mutableStateOf("") }
    var title by remember { mutableStateOf("") }
    var phone by remember { mutableStateOf("") }
    var priority by remember { mutableStateOf("Medium") }
    var valueStr by remember { mutableStateOf("") }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Add Walk-in / New Lead", fontWeight = FontWeight.Bold) },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Patient / Customer Name *") },
                    singleLine = true,
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("Inquiry / Treatment Title") },
                    placeholder = { Text("e.g. Dental Crown & Implant") },
                    singleLine = true,
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = phone,
                    onValueChange = { phone = it },
                    label = { Text("Phone Number") },
                    placeholder = { Text("+91 98765 43210") },
                    singleLine = true,
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier.fillMaxWidth()
                )
                OutlinedTextField(
                    value = valueStr,
                    onValueChange = { valueStr = it },
                    label = { Text("Estimated Value (₹ / $)") },
                    placeholder = { Text("15000") },
                    singleLine = true,
                    shape = RoundedCornerShape(10.dp),
                    modifier = Modifier.fillMaxWidth()
                )
            }
        },
        confirmButton = {
            Button(
                onClick = {
                    onSave(
                        name,
                        title.ifBlank { name },
                        phone.ifBlank { null },
                        priority,
                        valueStr.toDoubleOrNull() ?: 0.0
                    )
                },
                enabled = name.isNotBlank(),
                colors = ButtonDefaults.buttonColors(containerColor = DentalColors.Teal600),
                shape = RoundedCornerShape(8.dp)
            ) {
                Text("Create Lead", fontWeight = FontWeight.Bold)
            }
        },
        dismissButton = {
            OutlinedButton(onClick = onDismiss, shape = RoundedCornerShape(8.dp)) {
                Text("Cancel")
            }
        }
    )
}

@Composable
private fun LeadRow(
    lead: Lead,
    onStatusClick: () -> Unit,
    onCockpitClick: () -> Unit,
    onComposeClick: () -> Unit,
    onCallClick: () -> Unit,
    onWhatsAppClick: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface
        ),
        border = CardDefaults.outlinedCardBorder().copy(
            brush = SolidColor(MaterialTheme.colorScheme.outlineVariant.copy(alpha = 0.6f))
        )
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.Top
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = lead.title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = MaterialTheme.colorScheme.onSurface
                    )
                    Text(
                        text = "👤 ${lead.name}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant
                    )
                    lead.phone?.let {
                        Text(
                            text = "📞 $it",
                            style = MaterialTheme.typography.bodySmall,
                            color = DentalColors.Teal700,
                            fontWeight = FontWeight.Medium
                        )
                    }
                }

                // Interactive Status Badge (Tapping opens quick stage picker)
                val (badgeBg, badgeTextColor) = when (lead.status.lowercase()) {
                    "won", "processed" -> DentalColors.StatusHealthyBg to DentalColors.StatusHealthy
                    "qualified" -> DentalColors.StatusCrownBg to DentalColors.StatusCrown
                    "lost" -> MaterialTheme.colorScheme.errorContainer to MaterialTheme.colorScheme.error
                    else -> DentalColors.Teal50 to DentalColors.Teal900
                }

                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(badgeBg)
                        .clickable { onStatusClick() }
                        .padding(horizontal = 10.dp, vertical = 5.dp)
                ) {
                    Text(
                        text = "${lead.status} ▾",
                        style = MaterialTheme.typography.labelSmall,
                        fontWeight = FontWeight.Bold,
                        color = badgeTextColor
                    )
                }
            }

            // 1-Tap SIM Calling, WhatsApp, and Cockpit Action Buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                Button(
                    onClick = onCallClick,
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = DentalColors.Teal700
                    ),
                    modifier = Modifier.weight(1f).height(38.dp)
                ) {
                    Text("📞 Call", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                }

                Button(
                    onClick = onWhatsAppClick,
                    shape = RoundedCornerShape(8.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = DentalColors.Teal600
                    ),
                    modifier = Modifier.weight(1f).height(38.dp)
                ) {
                    Text("💬 WhatsApp", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                }

                OutlinedButton(
                    onClick = onCockpitClick,
                    shape = RoundedCornerShape(8.dp),
                    modifier = Modifier.height(38.dp)
                ) {
                    Text("📝 Notes", fontSize = 12.sp)
                }
            }
        }
    }
}
