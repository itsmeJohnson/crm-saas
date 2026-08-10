package com.crm.mobile.feature.dental

import androidx.compose.ui.graphics.Color
import com.crm.mobile.core.design.DentalColors
import com.squareup.moshi.JsonClass

enum class ToothStatus(val label: String, val color: Color, val bgColor: Color) {
    HEALTHY("Healthy", DentalColors.StatusHealthy, DentalColors.StatusHealthyBg),
    CARIES("Caries/Cavity", DentalColors.StatusCaries, DentalColors.StatusCariesBg),
    FILLING("Composite Fill", Color(0xFF0284C7), Color(0xFFE0F2FE)),
    CROWN("Zirconia Crown", DentalColors.StatusCrown, DentalColors.StatusCrownBg),
    RCT("Root Canal", DentalColors.StatusRCT, DentalColors.StatusRCTBg),
    IMPLANT("Implant", Color(0xFF0D9488), Color(0xFFCCFBF1)),
    MISSING("Missing", DentalColors.StatusMissing, DentalColors.StatusMissingBg),
    BRIDGE("Bridge Unit", Color(0xFFD97706), Color(0xFFFEF3C7))
}

@JsonClass(generateAdapter = true)
data class ToothCondition(
    val toothNumber: Int, // FDI notation: 11-18, 21-28, 31-38, 41-48
    val universalNumber: Int? = null, // Universal 1-32
    val status: String = "HEALTHY",
    val notes: String = "",
    val surfaces: String = "", // O, M, D, B, L
    val updatedAt: String = ""
) {
    fun getToothStatus(): ToothStatus = try {
        ToothStatus.valueOf(status)
    } catch (e: Exception) {
        ToothStatus.HEALTHY
    }
}

enum class AppointmentStatus(val label: String, val color: Color, val bgColor: Color) {
    SCHEDULED("Scheduled", Color(0xFF0284C7), Color(0xFFE0F2FE)),
    WAITING("Waiting in Lounge", Color(0xFFF59E0B), Color(0xFFFEF3C7)),
    IN_CHAIR("In Operatory Chair", Color(0xFF10B981), Color(0xFFD1FAE5)),
    COMPLETED("Completed", Color(0xFF64748B), Color(0xFFF1F5F9)),
    CANCELLED("Cancelled", Color(0xFFEF4444), Color(0xFFFEE2E2))
}

@JsonClass(generateAdapter = true)
data class DentalPatient(
    val id: String,
    val patientCode: String, // e.g. #DEN-1042
    val fullName: String,
    val phone: String,
    val age: Int,
    val gender: String,
    val bloodGroup: String = "O+",
    val medicalAlerts: List<String> = emptyList(), // e.g. ["Penicillin Allergy", "Hypertensive"]
    val chiefComplaint: String = "Routine dental checkup",
    val lastVisit: String = "Today",
    val nextRecallDate: String? = null,
    val ongoingTreatment: String? = null,
    val totalBilled: Double = 0.0,
    val outstandingBalance: Double = 0.0,
    val teethConditions: Map<Int, ToothCondition> = emptyMap(),
    val notes: String = ""
)

@JsonClass(generateAdapter = true)
data class DentalAppointment(
    val id: String,
    val patientId: String,
    val patientName: String,
    val patientPhone: String,
    val doctorName: String,
    val chair: String, // e.g. "Chair 1 (General)", "Chair 2 (Surgery/Ortho)"
    val procedure: String,
    val timeSlot: String, // e.g. "10:30 AM"
    val date: String, // e.g. "Today, Aug 9"
    val durationMinutes: Int = 45,
    val status: String = "SCHEDULED",
    val notes: String = ""
) {
    fun getApptStatus(): AppointmentStatus = try {
        AppointmentStatus.valueOf(status)
    } catch (e: Exception) {
        AppointmentStatus.SCHEDULED
    }
}

@JsonClass(generateAdapter = true)
data class TreatmentStep(
    val stepNumber: Int,
    val title: String,
    val isCompleted: Boolean = false,
    val completedDate: String? = null
)

@JsonClass(generateAdapter = true)
data class DentalTreatmentPlan(
    val id: String,
    val patientId: String,
    val patientName: String,
    val procedureName: String,
    val category: String, // Endodontics, Implantology, Orthodontics, etc.
    val toothNumbers: List<Int> = emptyList(),
    val totalCost: Double,
    val paidAmount: Double,
    val startDate: String,
    val status: String = "IN_PROGRESS", // PLANNED, IN_PROGRESS, COMPLETED
    val steps: List<TreatmentStep> = emptyList()
)

@JsonClass(generateAdapter = true)
data class DentalInvoice(
    val id: String,
    val invoiceNumber: String,
    val patientName: String,
    val procedureSummary: String,
    val amount: Double,
    val paidAmount: Double,
    val status: String = "PAID", // PAID, PARTIAL, DUE
    val paymentMethod: String = "UPI / Card",
    val date: String = "Aug 9, 2026"
)

@JsonClass(generateAdapter = true)
data class DentalRecall(
    val id: String,
    val patientName: String,
    val patientPhone: String,
    val recallType: String, // 6-Month Hygiene, Ortho Wire Change, Implant Checkup, Crown Review
    val dueDate: String,
    val status: String = "PENDING", // PENDING, SENT, SCHEDULED
    val lastContacted: String? = null
)

data class DentalProcedureCatalogItem(
    val name: String,
    val category: String,
    val basePrice: Double,
    val estimatedDuration: String,
    val commonSteps: List<String>
)

data class ClinicDashboardStats(
    val todayAppointmentsCount: Int,
    val inChairCount: Int,
    val pendingTreatmentsCount: Int,
    val todayCollections: Double,
    val dueRecallsCount: Int
)
