package com.crm.mobile.core.push

import com.crm.mobile.core.session.SessionManager
import io.mockk.coEvery
import io.mockk.coVerify
import io.mockk.mockk
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class PushRegistrarTest {

    private class FakeDeviceApi : DeviceApi {
        var registered: DeviceRegisterReq? = null
        var unregistered: DeviceUnregisterReq? = null
        override suspend fun register(body: DeviceRegisterReq): DeviceRegisterResp {
            registered = body; return DeviceRegisterResp("dev-1", body.platform)
        }
        override suspend fun unregister(body: DeviceUnregisterReq) { unregistered = body }
    }

    @Test
    fun registerNow_registers_fcm_token_and_persists_it() = runTest {
        val api = FakeDeviceApi()
        val session = mockk<SessionManager>(relaxed = true)
        val reg = PushRegistrar(api, session, FcmTokenProvider { "tok-abc" })

        assertTrue(reg.registerNow("Pixel 8"))
        assertEquals("tok-abc", api.registered?.token)
        assertEquals("fcm", api.registered?.platform)
        assertEquals("Pixel 8", api.registered?.device_name)
        coVerify { session.savePushToken("tok-abc") }
    }

    @Test
    fun registerNow_without_a_token_is_a_silent_noop() = runTest {
        val api = FakeDeviceApi()
        val session = mockk<SessionManager>(relaxed = true)
        val reg = PushRegistrar(api, session, FcmTokenProvider { null })

        assertFalse(reg.registerNow())
        assertNull(api.registered)
        coVerify(exactly = 0) { session.savePushToken(any()) }
    }

    @Test
    fun unregisterNow_unregisters_stored_token_then_clears_it() = runTest {
        val api = FakeDeviceApi()
        val session = mockk<SessionManager>(relaxed = true)
        coEvery { session.pushToken() } returns "tok-xyz"
        val reg = PushRegistrar(api, session, FcmTokenProvider { "tok-xyz" })

        reg.unregisterNow()
        assertEquals("tok-xyz", api.unregistered?.token)
        coVerify { session.clearPushToken() }
    }

    @Test
    fun unregisterNow_without_a_stored_token_is_a_noop() = runTest {
        val api = FakeDeviceApi()
        val session = mockk<SessionManager>(relaxed = true)
        coEvery { session.pushToken() } returns null
        val reg = PushRegistrar(api, session, FcmTokenProvider { null })

        reg.unregisterNow()
        assertNull(api.unregistered)
        coVerify(exactly = 0) { session.clearPushToken() }
    }
}
