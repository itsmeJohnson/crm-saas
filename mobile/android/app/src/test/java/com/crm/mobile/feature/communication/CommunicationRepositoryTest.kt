package com.crm.mobile.feature.communication

import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.IOException

class CommunicationRepositoryTest {

    private class FakeApi(val fail: Boolean = false) : CommunicationApi {
        var smsReq: SmsSendReq? = null
        var waReq: WaSendReq? = null
        var emailReq: EmailSendReq? = null
        override suspend fun sendSms(body: SmsSendReq): Map<String, Any?> {
            if (fail) throw IOException("Unable to resolve host"); smsReq = body; return emptyMap()
        }
        override suspend fun sendWhatsApp(body: WaSendReq): Map<String, Any?> { waReq = body; return emptyMap() }
        override suspend fun sendEmail(body: EmailSendReq): Map<String, Any?> { emailReq = body; return emptyMap() }
    }

    @Test
    fun sms_routes_to_sms_endpoint_only() = runTest {
        val api = FakeApi()
        val r = CommunicationRepository(api).send(Channel.SMS, "lead-1", "", "hi there")
        assertTrue(r.isSuccess)
        assertEquals("hi there", api.smsReq?.body)
        assertEquals("lead-1", api.smsReq?.lead_id)
        assertNull(api.waReq); assertNull(api.emailReq)
    }

    @Test
    fun whatsapp_routes_to_whatsapp_endpoint() = runTest {
        val api = FakeApi()
        CommunicationRepository(api).send(Channel.WHATSAPP, "lead-1", "", "yo")
        assertEquals("yo", api.waReq?.body)
        assertNull(api.smsReq)
    }

    @Test
    fun email_defaults_blank_subject() = runTest {
        val api = FakeApi()
        CommunicationRepository(api).send(Channel.EMAIL, "lead-1", "", "hello")
        assertEquals("(no subject)", api.emailReq?.subject)
        assertEquals("hello", api.emailReq?.body)
    }

    @Test
    fun offline_send_fails_with_friendly_message() = runTest {
        val r = CommunicationRepository(FakeApi(fail = true)).send(Channel.SMS, "lead-1", "", "hi")
        assertTrue(r.isFailure)
        assertTrue(r.exceptionOrNull()?.message?.contains("offline") == true)
    }
}
