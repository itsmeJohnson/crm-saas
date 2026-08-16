package com.crm.mobile.feature.cockpit

import androidx.room.Dao
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.OnConflictStrategy
import androidx.room.PrimaryKey
import androidx.room.Query
import com.crm.mobile.core.session.SessionManager
import com.squareup.moshi.JsonClass
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import retrofit2.http.Body
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.Path
import javax.inject.Inject
import javax.inject.Singleton

// ---- Wire DTOs (reuse the backend dialer + follow-up + pipelines contracts) ----

@JsonClass(generateAdapter = true)
data class CockpitLeadDto(
    val id: String,
    val first_name: String?,
    val last_name: String?,
    val title: String,
    val phone: String?,        // server-masked for telecallers
    val email: String?,
    val city: String?,
    val status: String,
    val value: Double?,
)

@JsonClass(generateAdapter = true)
data class PipelineStageDto(val id: String, val name: String, val order_position: Int)

@JsonClass(generateAdapter = true)
data class NextLeadReq(val collective_pooling: Boolean = false)

@JsonClass(generateAdapter = true)
data class CallReq(
    val provider: String,
    val agent_phone_number: String?,
    val knowlarity_api_key: String? = null,
    val knowlarity_srn: String? = null,
    val myop_x_api_key: String? = null,
    val myop_secret_key: String? = null,
    val myop_company_id: String? = null,
    val myop_caller_id: String? = null,
)

@JsonClass(generateAdapter = true)
data class DispositionReq(
    val status: String,
    val remarks: String,
    val custom_pipeline_stage_id: String? = null,
)

@JsonClass(generateAdapter = true)
data class FollowUpReq(
    val outcome: String,
    val follow_up_type: String = "call",
    val next_follow_up_at: String,
    val priority: String = "Medium",
    val remarks: String? = null,
    val reminder_minutes_before: Int? = null,
    val create_calendar_event: Boolean = false,
)

interface CockpitApi {
    @POST("dialer/next-lead")
    suspend fun nextLead(@Body body: NextLeadReq = NextLeadReq()): CockpitLeadDto

    @POST("dialer/leads/{id}/call")
    suspend fun call(@Path("id") id: String, @Body body: CallReq): CockpitLeadDto

    @POST("dialer/leads/{id}/disposition")
    suspend fun disposition(@Path("id") id: String, @Body body: DispositionReq): CockpitLeadDto

    @POST("leads/{id}/follow-up")
    suspend fun followUp(@Path("id") id: String, @Body body: FollowUpReq): Map<String, Any?>

    @GET("pipelines/")
    suspend fun stages(): List<PipelineStageDto>
}

// ---- Local cache for the pipeline stage picker (works offline) ----

@Entity(tableName = "pipeline_stages")
data class PipelineStageEntity(@PrimaryKey val id: String, val name: String, val orderPosition: Int)

@Dao
interface PipelineStageDao {
    @Query("SELECT * FROM pipeline_stages ORDER BY orderPosition")
    fun observe(): Flow<List<PipelineStageEntity>>

    @Insert(onConflict = OnConflictStrategy.REPLACE)
    suspend fun upsertAll(stages: List<PipelineStageEntity>)
}

// ---- Domain ----

data class CockpitLead(
    val id: String,
    val name: String,
    val title: String,
    val phone: String?,
    val email: String?,
    val city: String?,
    val status: String,
    val value: Double?,
)

data class Stage(val id: String, val name: String)

data class CallResult(val ok: Boolean, val message: String?)

private fun CockpitLeadDto.toDomain() = CockpitLead(
    id = id,
    name = listOfNotNull(first_name, last_name).joinToString(" ").ifBlank { "—" },
    title = title, phone = phone, email = email, city = city, status = status, value = value,
)

@Singleton
class CockpitRepository @Inject constructor(
    private val api: CockpitApi,
    private val stageDao: PipelineStageDao,
    private val session: SessionManager,
) {
    val stages: Flow<List<Stage>> = stageDao.observe().map { list -> list.map { Stage(it.id, it.name) } }

    suspend fun refreshStages() = runCatching {
        stageDao.upsertAll(api.stages().map { PipelineStageEntity(it.id, it.name, it.order_position) })
    }

    suspend fun nextLead(collectivePooling: Boolean = false): Result<CockpitLead?> =
        runCatching { api.nextLead(NextLeadReq(collectivePooling)).toDomain() }

    /** Server-side click-to-call (keeps the customer number masked). */
    suspend fun call(leadId: String): CallResult {
        val tel = session.telephony()
        if (!tel.isConfigured) {
            return CallResult(false, "Calling isn't configured. Set your provider, keys and agent phone in Settings.")
        }
        return runCatching {
            api.call(leadId, CallReq(
                provider = tel.provider,
                agent_phone_number = tel.agentPhone,
                knowlarity_api_key = tel.apiKey,
                knowlarity_srn = tel.srn,
                myop_x_api_key = tel.myopXApiKey,
                myop_secret_key = tel.myopSecretKey,
                myop_company_id = tel.myopCompanyId,
                myop_caller_id = tel.myopCallerId,
            ))
            CallResult(true, null)
        }.getOrElse { CallResult(false, it.toUserMessage()) }
    }

    suspend fun submitDisposition(leadId: String, status: String, remarks: String, stageId: String?): Result<Unit> =
        runCatching { api.disposition(leadId, DispositionReq(status, remarks, stageId)); Unit }

    suspend fun submitFollowUp(
        leadId: String, outcome: String, nextAtIso: String, priority: String,
        remarks: String?, reminderMinutes: Int?, calendarEvent: Boolean,
    ): Result<Unit> = runCatching {
        api.followUp(leadId, FollowUpReq(
            outcome = outcome, next_follow_up_at = nextAtIso, priority = priority,
            remarks = remarks, reminder_minutes_before = reminderMinutes,
            create_calendar_event = calendarEvent,
        )); Unit
    }
}

private fun Throwable.toUserMessage(): String = when {
    message?.contains("Unable to resolve host") == true -> "You're offline — can't place the call."
    message?.contains("403") == true -> "You can only call leads assigned to you."
    else -> "Couldn't start the call. Please try again."
}
