package com.crm.mobile.feature.dental

import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query

// ---- Live CRM DTOs ----

@JsonClass(generateAdapter = true)
data class CrmContactDto(
    val id: String,
    val first_name: String,
    val last_name: String,
    val email: String? = null,
    val phone: String? = null,
    val job_title: String? = null,
    val tags: List<String>? = null,
    val custom_fields: Map<String, Any?>? = null,
    val created_at: String? = null
)

@JsonClass(generateAdapter = true)
data class CrmContactCreateDto(
    val first_name: String,
    val last_name: String,
    val phone: String? = null,
    val email: String? = null,
    val job_title: String? = "Dental Patient",
    val tags: List<String>? = listOf("Dental", "Patient"),
    val custom_fields: Map<String, Any?>? = null
)

@JsonClass(generateAdapter = true)
data class CrmContactUpdateDto(
    val first_name: String? = null,
    val last_name: String? = null,
    val phone: String? = null,
    val custom_fields: Map<String, Any?>? = null
)

@JsonClass(generateAdapter = true)
data class CrmEventDto(
    val id: String,
    val title: String,
    val description: String? = null,
    val start_time: String? = null,
    val end_time: String? = null,
    val location: String? = null,
    val event_type: String? = "Appointment",
    val status: String? = "SCHEDULED"
)

@JsonClass(generateAdapter = true)
data class CrmEventCreateDto(
    val title: String,
    val description: String? = null,
    val start_time: String,
    val end_time: String,
    val location: String? = "Chair 1 (Operatory)",
    val event_type: String = "Dental Appointment"
)

@JsonClass(generateAdapter = true)
data class CrmEventUpdateDto(
    val title: String? = null,
    val description: String? = null,
    val location: String? = null,
    val event_type: String? = null
)

@JsonClass(generateAdapter = true)
data class CrmTaskDto(
    val id: String,
    val title: String,
    val description: String? = null,
    val due_date: String? = null,
    val status: String = "Pending",
    val priority: String? = "Medium",
    val contact_id: String? = null
)

@JsonClass(generateAdapter = true)
data class CrmActivityCreateDto(
    val activity_type: String = "Dental Note",
    val subject: String,
    val description: String? = null,
    val contact_id: String? = null,
    val status: String = "Completed"
)

@JsonClass(generateAdapter = true)
data class CrmActivityDto(
    val id: String,
    val activity_type: String,
    val subject: String,
    val description: String? = null,
    val status: String,
    val created_at: String? = null
)

interface DentalApi {
    @GET("contacts/")
    suspend fun listContacts(@Query("limit") limit: Int = 100): List<CrmContactDto>

    @POST("contacts/")
    suspend fun createContact(@Body body: CrmContactCreateDto): CrmContactDto

    @PATCH("contacts/{id}")
    suspend fun updateContact(@Path("id") id: String, @Body body: CrmContactUpdateDto): CrmContactDto

    @GET("calendar/events")
    suspend fun listEvents(
        @Query("date_from") dateFrom: String? = null,
        @Query("date_to") dateTo: String? = null
    ): List<CrmEventDto>

    @POST("calendar/events")
    suspend fun createEvent(@Body body: CrmEventCreateDto): CrmEventDto

    @PATCH("calendar/events/{id}")
    suspend fun updateEvent(@Path("id") id: String, @Body body: CrmEventUpdateDto): CrmEventDto

    @GET("tasks/")
    suspend fun listTasks(@Query("limit") limit: Int = 100): List<CrmTaskDto>

    @PATCH("tasks/{id}")
    suspend fun updateTask(@Path("id") id: String, @Body body: Map<String, String>): CrmTaskDto

    @POST("activities/")
    suspend fun logActivity(@Body body: CrmActivityCreateDto): CrmActivityDto
}
