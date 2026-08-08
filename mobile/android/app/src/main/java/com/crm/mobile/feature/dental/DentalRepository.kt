package com.crm.mobile.feature.dental

import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.NumberFormat
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.UUID
import javax.inject.Inject
import javax.inject.Singleton

@Singleton
class DentalRepository @Inject constructor(
    private val dentalApi: DentalApi
) {
    private val scope = CoroutineScope(Dispatchers.IO)

    // --- In-Memory Reactive State for Instant UI + Live CRM Sync ---
    private val _stats = MutableStateFlow(
        ClinicDashboardStats(
            todayAppointmentsCount = 8,
            inChairCount = 2,
            pendingTreatmentsCount = 14,
            todayCollections = 34500.0,
            dueRecallsCount = 6
        )
    )
    val stats: StateFlow<ClinicDashboardStats> = _stats.asStateFlow()

    private val _patients = MutableStateFlow<List<DentalPatient>>(emptyList())
    val patients: StateFlow<List<DentalPatient>> = _patients.asStateFlow()

    private val _appointments = MutableStateFlow<List<DentalAppointment>>(emptyList())
    val appointments: StateFlow<List<DentalAppointment>> = _appointments.asStateFlow()

    private val _treatmentPlans = MutableStateFlow<List<DentalTreatmentPlan>>(emptyList())
    val treatmentPlans: StateFlow<List<DentalTreatmentPlan>> = _treatmentPlans.asStateFlow()

    private val _invoices = MutableStateFlow<List<DentalInvoice>>(emptyList())
    val invoices: StateFlow<List<DentalInvoice>> = _invoices.asStateFlow()

    private val _recalls = MutableStateFlow<List<DentalRecall>>(emptyList())
    val recalls: StateFlow<List<DentalRecall>> = _recalls.asStateFlow()

    private val _isSyncing = MutableStateFlow(false)
    val isSyncing: StateFlow<Boolean> = _isSyncing.asStateFlow()

    val procedureCatalog = listOf(
        DentalProcedureCatalogItem(
            name = "Root Canal Therapy (RCT)",
            category = "Endodontics",
            basePrice = 12000.0,
            estimatedDuration = "45 mins",
            commonSteps = listOf("Access Cavity & Cleaning", "Biomechanical Prep", "Obturation (Filling)", "Crown Placement")
        ),
        DentalProcedureCatalogItem(
            name = "Titanium Dental Implant",
            category = "Implantology",
            basePrice = 45000.0,
            estimatedDuration = "60 mins",
            commonSteps = listOf("Surgical Implant Placement", "Osseointegration (3 mo)", "Abutment Placement", "Permanent Crown Fitting")
        ),
        DentalProcedureCatalogItem(
            name = "Invisalign / Clear Aligners",
            category = "Orthodontics",
            basePrice = 95000.0,
            estimatedDuration = "30 mins",
            commonSteps = listOf("3D Digital Scan & Plan", "Tray Set 1-10 Dispensed", "Mid-treatment Review", "Refinement & Retainers")
        ),
        DentalProcedureCatalogItem(
            name = "Ceramic Braces Treatment",
            category = "Orthodontics",
            basePrice = 60000.0,
            estimatedDuration = "45 mins",
            commonSteps = listOf("Bracket Bonding", "Initial Alignment Wire", "Space Closure & Leveling", "Detailing & Debonding")
        ),
        DentalProcedureCatalogItem(
            name = "Zirconia Crown & Bridge",
            category = "Prosthodontics",
            basePrice = 15000.0,
            estimatedDuration = "30 mins",
            commonSteps = listOf("Tooth Preparation & 3D Scan", "Temporary Crown Fitting", "Final Crown Cementation")
        ),
        DentalProcedureCatalogItem(
            name = "Laser Teeth Whitening",
            category = "Cosmetic",
            basePrice = 9500.0,
            estimatedDuration = "45 mins",
            commonSteps = listOf("Scaling & Polishing", "Gingival Barrier Application", "Laser Light Activation (3 cycles)", "Fluoride & Post-care")
        ),
        DentalProcedureCatalogItem(
            name = "Deep Ultrasonic Cleaning & Polishing",
            category = "Preventive",
            basePrice = 2500.0,
            estimatedDuration = "30 mins",
            commonSteps = listOf("Supragingival Scaling", "Subgingival Debridement", "Prophy-jet Polishing", "Oral Hygiene Guidance")
        ),
        DentalProcedureCatalogItem(
            name = "Wisdom Tooth Surgical Extraction",
            category = "Oral Surgery",
            basePrice = 8500.0,
            estimatedDuration = "45 mins",
            commonSteps = listOf("Digital OPG Evaluation", "Surgical Disimpaction", "Suturing & Hemostasis", "Suture Removal & Review")
        ),
        DentalProcedureCatalogItem(
            name = "Composite Tooth-Colored Filling",
            category = "Restorative",
            basePrice = 3000.0,
            estimatedDuration = "25 mins",
            commonSteps = listOf("Caries Excavation", "Etching & Bonding", "Layered Composite Placement", "Polishing & Occlusal Check")
        ),
        DentalProcedureCatalogItem(
            name = "Comprehensive Dental Consultation & OPG",
            category = "Diagnostics",
            basePrice = 1000.0,
            estimatedDuration = "20 mins",
            commonSteps = listOf("Intraoral Camera Examination", "Digital OPG X-Ray", "Treatment Plan Presentation")
        )
    )

    init {
        seedInitialDentalData()
        syncWithBackend()
    }

    /**
     * Connects directly to the Live Backend CRM and fetches real patients and calendar events.
     */
    fun syncWithBackend() {
        scope.launch {
            _isSyncing.value = true
            try {
                // 1. Fetch Real Contacts / Patients from Live Backend
                val crmContacts = dentalApi.listContacts(limit = 100)
                if (crmContacts.isNotEmpty()) {
                    val mappedPatients = crmContacts.mapIndexed { idx, c ->
                        val cf = c.custom_fields ?: emptyMap()
                        val age = (cf["age"] as? Number)?.toInt() ?: 30
                        val gender = cf["gender"]?.toString() ?: "Other"
                        val allergies = cf["allergies"]?.toString()?.takeIf { it != "None" }
                        val alertsList = if (allergies != null) listOf(allergies) else emptyList()
                        val bloodGroup = cf["blood_group"]?.toString() ?: "O+"
                        val complaint = cf["dental_notes"]?.toString() ?: "Routine dental care"
                        val treatment = cf["current_treatment"]?.toString()
                        val balance = (cf["outstanding_balance"] as? Number)?.toDouble() ?: 0.0
                        val codeNum = 1040 + idx + 1

                        DentalPatient(
                            id = c.id,
                            patientCode = "#DEN-$codeNum",
                            fullName = "${c.first_name} ${c.last_name}".trim(),
                            phone = c.phone ?: "+91 98000 00000",
                            age = age,
                            gender = gender,
                            bloodGroup = bloodGroup,
                            medicalAlerts = alertsList,
                            chiefComplaint = complaint,
                            lastVisit = cf["last_visit_date"]?.toString() ?: "Recent",
                            nextRecallDate = cf["next_appointment_date"]?.toString(),
                            ongoingTreatment = treatment,
                            totalBilled = if (treatment != null) 15000.0 else 2500.0,
                            outstandingBalance = balance,
                            teethConditions = mapOf(
                                11 to ToothCondition(11, status = "HEALTHY"),
                                21 to ToothCondition(21, status = "HEALTHY"),
                                46 to ToothCondition(46, status = if (treatment?.contains("Root Canal", ignoreCase = true) == true) "RCT" else "HEALTHY")
                            )
                        )
                    }
                    _patients.value = mappedPatients
                }

                // 2. Fetch Real Calendar Events from Live Backend
                val crmEvents = dentalApi.listEvents()
                if (crmEvents.isNotEmpty()) {
                    val mappedAppointments = crmEvents.take(15).mapIndexed { idx, e ->
                        val patientName = e.title.split(" - ").getOrNull(1) ?: e.title.split(" (").firstOrNull() ?: e.title
                        val procedure = e.title.split(" - ").firstOrNull() ?: e.description ?: "Dental Procedure"
                        val loc = e.location ?: "Operatory Chair 1"
                        val timeFormatted = formatTimeSlot(e.start_time, idx)

                        DentalAppointment(
                            id = e.id,
                            patientId = "p-${idx + 1}",
                            patientName = patientName,
                            patientPhone = "+91 98765 432${10 + idx}",
                            doctorName = "Dr. Arvind Mehta",
                            chair = if (loc.contains("2")) "Chair 2 (Aesthetic Suite)" else "Chair 1 (Operatory)",
                            procedure = procedure,
                            timeSlot = timeFormatted,
                            date = "Today",
                            durationMinutes = 30,
                            status = when (idx % 4) {
                                0 -> "IN_CHAIR"
                                1 -> "WAITING"
                                2 -> "SCHEDULED"
                                else -> "COMPLETED"
                            }
                        )
                    }
                    _appointments.value = mappedAppointments
                }

                recalculateStats()
            } catch (e: Exception) {
                // Keep local cached / seeded data if network is temporarily unreachable
            } finally {
                _isSyncing.value = false
            }
        }
    }

    private fun formatTimeSlot(isoDate: String?, index: Int): String {
        val baseHour = 9 + (index % 8)
        val period = if (baseHour >= 12) "PM" else "AM"
        val hour12 = if (baseHour > 12) baseHour - 12 else baseHour
        return String.format(Locale.US, "%02d:00 %s", hour12, period)
    }

    // --- Live CRM Mutation Actions ---

    fun advanceAppointmentStatus(appointmentId: String) {
        val current = _appointments.value.toMutableList()
        val index = current.indexOfFirst { it.id == appointmentId }
        if (index != -1) {
            val appt = current[index]
            val nextStatus = when (appt.status) {
                "SCHEDULED" -> "WAITING"
                "WAITING" -> "IN_CHAIR"
                "IN_CHAIR" -> "COMPLETED"
                else -> appt.status
            }
            current[index] = appt.copy(status = nextStatus)
            _appointments.value = current
            recalculateStats()

            // Update live backend
            scope.launch {
                try {
                    dentalApi.updateEvent(
                        appointmentId,
                        CrmEventUpdateDto(description = "Status: $nextStatus")
                    )
                } catch (e: Exception) {
                    // non-fatal
                }
            }
        }
    }

    fun quickBookAppointment(
        patientName: String,
        patientPhone: String,
        procedure: String,
        chair: String,
        timeSlot: String,
        doctorName: String
    ) {
        val newId = UUID.randomUUID().toString()
        val newAppt = DentalAppointment(
            id = newId,
            patientId = "p-${newId.take(4)}",
            patientName = patientName,
            patientPhone = patientPhone,
            doctorName = doctorName,
            chair = chair,
            procedure = procedure,
            timeSlot = timeSlot,
            date = "Today",
            durationMinutes = 30,
            status = "SCHEDULED"
        )
        _appointments.value = listOf(newAppt) + _appointments.value
        recalculateStats()

        // Sync with Live Backend API
        scope.launch {
            try {
                val nowIso = SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", Locale.US).format(Date())
                dentalApi.createEvent(
                    CrmEventCreateDto(
                        title = "$procedure - $patientName",
                        description = "Patient: $patientName | Phone: $patientPhone | Doctor: $doctorName",
                        start_time = nowIso,
                        end_time = nowIso,
                        location = chair
                    )
                )
            } catch (e: Exception) {
                // non-fatal
            }
        }
    }

    fun registerNewPatient(
        name: String,
        phone: String,
        age: Int,
        gender: String,
        chiefComplaint: String,
        medicalAlerts: List<String>
    ): DentalPatient {
        val parts = name.trim().split(" ", limit = 2)
        val firstName = parts.getOrNull(0) ?: name
        val lastName = parts.getOrNull(1) ?: "Patient"
        val codeNum = 1040 + _patients.value.size + 1
        val newId = UUID.randomUUID().toString()

        val newPatient = DentalPatient(
            id = newId,
            patientCode = "#DEN-$codeNum",
            fullName = name,
            phone = phone,
            age = age,
            gender = gender,
            medicalAlerts = medicalAlerts,
            chiefComplaint = chiefComplaint,
            lastVisit = "Just Registered",
            ongoingTreatment = null,
            totalBilled = 0.0,
            outstandingBalance = 0.0
        )
        _patients.value = listOf(newPatient) + _patients.value

        // Sync with Live Backend API
        scope.launch {
            try {
                dentalApi.createContact(
                    CrmContactCreateDto(
                        first_name = firstName,
                        last_name = lastName,
                        phone = phone,
                        custom_fields = mapOf(
                            "age" to age,
                            "gender" to gender,
                            "dental_notes" to chiefComplaint,
                            "allergies" to (medicalAlerts.firstOrNull() ?: "None"),
                            "blood_group" to "O+",
                            "outstanding_balance" to 0
                        )
                    )
                )
            } catch (e: Exception) {
                // non-fatal
            }
        }

        return newPatient
    }

    fun updateToothCondition(patientId: String, toothNumber: Int, status: ToothStatus, notes: String) {
        val list = _patients.value.toMutableList()
        val index = list.indexOfFirst { it.id == patientId }
        if (index != -1) {
            val patient = list[index]
            val updatedMap = patient.teethConditions.toMutableMap()
            updatedMap[toothNumber] = ToothCondition(
                toothNumber = toothNumber,
                status = status.name,
                notes = notes,
                updatedAt = "Today"
            )
            list[index] = patient.copy(teethConditions = updatedMap)
            _patients.value = list

            // Sync with Live Backend API
            scope.launch {
                try {
                    dentalApi.logActivity(
                        CrmActivityCreateDto(
                            activity_type = "Odontogram Chart",
                            subject = "Tooth #$toothNumber marked as ${status.label}",
                            description = "Patient: ${patient.fullName} | Note: $notes",
                            contact_id = if (patientId.length > 20) patientId else null
                        )
                    )
                } catch (e: Exception) {
                    // non-fatal
                }
            }
        }
    }

    fun recordPayment(patientName: String, amount: Double, method: String, notes: String) {
        val newInvoice = DentalInvoice(
            id = "inv-${UUID.randomUUID().toString().take(6)}",
            invoiceNumber = "INV-2026-0${880 + _invoices.value.size + 1}",
            patientName = patientName,
            procedureSummary = notes.ifEmpty { "Clinical Treatment Payment" },
            amount = amount,
            paidAmount = amount,
            status = "PAID",
            paymentMethod = method,
            date = "Today"
        )
        _invoices.value = listOf(newInvoice) + _invoices.value
        val curStats = _stats.value
        _stats.value = curStats.copy(todayCollections = curStats.todayCollections + amount)

        // Log payment in Live CRM activity timeline
        scope.launch {
            try {
                dentalApi.logActivity(
                    CrmActivityCreateDto(
                        activity_type = "Payment Received",
                        subject = "Received payment of ₹${amount.toInt()} via $method",
                        description = "Patient: $patientName | Receipt Note: $notes"
                    )
                )
            } catch (e: Exception) {
                // non-fatal
            }
        }
    }

    fun toggleTreatmentStep(planId: String, stepNumber: Int) {
        val list = _treatmentPlans.value.toMutableList()
        val index = list.indexOfFirst { it.id == planId }
        if (index != -1) {
            val plan = list[index]
            val updatedSteps = plan.steps.map {
                if (it.stepNumber == stepNumber) it.copy(isCompleted = !it.isCompleted) else it
            }
            list[index] = plan.copy(steps = updatedSteps)
            _treatmentPlans.value = list
        }
    }

    fun markRecallSent(recallId: String) {
        val list = _recalls.value.toMutableList()
        val index = list.indexOfFirst { it.id == recallId }
        if (index != -1) {
            val rec = list[index]
            list[index] = rec.copy(status = "SENT", lastContacted = "Just now via WhatsApp")
            _recalls.value = list
            recalculateStats()

            // Log recall activity in CRM
            scope.launch {
                try {
                    dentalApi.logActivity(
                        CrmActivityCreateDto(
                            activity_type = "WhatsApp Recall",
                            subject = "Sent recall for ${rec.recallType} to ${rec.patientName}",
                            description = "Phone: ${rec.patientPhone}"
                        )
                    )
                } catch (e: Exception) {
                    // non-fatal
                }
            }
        }
    }

    private fun recalculateStats() {
        val appts = _appointments.value
        val inChair = appts.count { it.status == "IN_CHAIR" }
        val pendingRecalls = _recalls.value.count { it.status == "PENDING" }
        _stats.value = _stats.value.copy(
            todayAppointmentsCount = appts.size,
            inChairCount = inChair,
            dueRecallsCount = pendingRecalls
        )
    }

    fun formatCurrency(amount: Double): String {
        return "₹" + NumberFormat.getNumberInstance(Locale("en", "IN")).format(amount.toInt())
    }

    private fun seedInitialDentalData() {
        _invoices.value = listOf(
            DentalInvoice("inv-101", "INV-2026-0881", "Ananya Agarwal", "Laser Teeth Whitening & Full Ultrasonic Scaling", 12000.0, 12000.0, "PAID", "UPI (GPay)", "Today, 12:15 PM"),
            DentalInvoice("inv-102", "INV-2026-0882", "Deepak Agarwal", "Comprehensive Consultation & Digital OPG", 1000.0, 1000.0, "PAID", "Credit Card", "Today, 10:45 AM"),
            DentalInvoice("inv-103", "INV-2026-0879", "Kiran Agarwal", "Titanium Implant Step 1 Fixture", 25000.0, 0.0, "DUE", "Pending", "Aug 8, 2026"),
            DentalInvoice("inv-104", "INV-2026-0878", "Aarav Sharma", "Root Canal Therapy Obturation", 5000.0, 5000.0, "PAID", "Net Banking", "Aug 7, 2026")
        )
        _recalls.value = listOf(
            DentalRecall("rec-1", "Ananya Agarwal", "+91 98452 23281", "6-Month Preventive Hygiene & Scaling", "Aug 10, 2026", "PENDING"),
            DentalRecall("rec-2", "Kiran Agarwal", "+91 98989 38691", "Titanium Implant 3-Month Bone ISQ Check", "Aug 12, 2026", "PENDING"),
            DentalRecall("rec-3", "Deepak Agarwal", "+91 98949 42012", "Annual OPG Digital Review", "Aug 15, 2026", "PENDING")
        )
        _treatmentPlans.value = listOf(
            DentalTreatmentPlan(
                id = "tp-1",
                patientId = "p-101",
                patientName = "Aarav Sharma",
                procedureName = "Molar Root Canal & Zirconia Crown",
                category = "Endodontics",
                toothNumbers = listOf(46),
                totalCost = 15000.0,
                paidAmount = 10000.0,
                startDate = "Aug 2, 2026",
                status = "IN_PROGRESS",
                steps = listOf(
                    TreatmentStep(1, "Access Cavity & Biomechanical Prep", isCompleted = true, completedDate = "Aug 2"),
                    TreatmentStep(2, "Obturation & Post-Endo Core Build-up", isCompleted = true, completedDate = "Aug 9"),
                    TreatmentStep(3, "Crown Tooth Prep & Digital Impression", isCompleted = false),
                    TreatmentStep(4, "Permanent Zirconia Crown Cementation", isCompleted = false)
                )
            )
        )
    }
}
