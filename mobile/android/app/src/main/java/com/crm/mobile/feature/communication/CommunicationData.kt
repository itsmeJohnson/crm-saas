package com.crm.mobile.feature.communication

import com.squareup.moshi.JsonClass
import retrofit2.http.Body
import retrofit2.http.POST
import javax.inject.Inject
import javax.inject.Singleton

// ---- Request DTOs (reuse the backend send contracts; lead_id lets the server
// resolve the recipient + attach to the lead's timeline — masking-safe) ----

@JsonClass(generateAdapter = true)
data class SmsSendReq(val body: String, val lead_id: String)

@JsonClass(generateAdapter = true)
data class WaSendReq(val body: String, val lead_id: String)

@JsonClass(generateAdapter = true)
data class EmailSendReq(val subject: String, val body: String, val lead_id: String)

interface CommunicationApi {
    @POST("sms/send")
    suspend fun sendSms(@Body body: SmsSendReq): Map<String, Any?>

    @POST("whatsapp/send")
    suspend fun sendWhatsApp(@Body body: WaSendReq): Map<String, Any?>

    @POST("email/send")
    suspend fun sendEmail(@Body body: EmailSendReq): Map<String, Any?>
}

enum class Channel { SMS, WHATSAPP, EMAIL }

@Singleton
class CommunicationRepository @Inject constructor(private val api: CommunicationApi) {

    /** Sends via the chosen channel to a lead; the backend logs it to the
     *  timeline. Returns a friendly error message on failure. */
    suspend fun send(channel: Channel, leadId: String, subject: String, body: String): Result<Unit> = runCatching {
        when (channel) {
            Channel.SMS -> api.sendSms(SmsSendReq(body, leadId))
            Channel.WHATSAPP -> api.sendWhatsApp(WaSendReq(body, leadId))
            Channel.EMAIL -> api.sendEmail(EmailSendReq(subject.ifBlank { "(no subject)" }, body, leadId))
        }
        Unit
    }.recoverCatching { throw IllegalStateException(it.toUserMessage(), it) }
}

private fun Throwable.toUserMessage(): String = when {
    message?.contains("Unable to resolve host") == true -> "You're offline — can't send right now."
    message?.contains("400") == true || message?.contains("422") == true ->
        "This channel isn't configured, or the lead has no number/email."
    else -> "Couldn't send. Please try again."
}
