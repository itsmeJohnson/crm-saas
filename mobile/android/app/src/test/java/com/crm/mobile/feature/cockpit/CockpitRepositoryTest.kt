package com.crm.mobile.feature.cockpit

import com.crm.mobile.core.session.SessionManager
import com.crm.mobile.core.session.TelephonyCreds
import io.mockk.coEvery
import io.mockk.mockk
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flowOf
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Pins the cockpit's routing: Picked/other outcomes → /disposition, a Follow-up
 *  outcome → /follow-up (which fans out to task+reminder+calendar server-side),
 *  and the "calling not configured" guard never hits the network. */
class CockpitRepositoryTest {

    private class FakeApi : CockpitApi {
        var dispositionReq: DispositionReq? = null
        var followUpReq: FollowUpReq? = null
        var callInvoked = false
        private val lead = CockpitLeadDto("1", "A", "B", "T", "+91***", "e", "c", "New", 1.0)
        override suspend fun nextLead(body: NextLeadReq) = lead
        override suspend fun call(id: String, body: CallReq): CockpitLeadDto { callInvoked = true; return lead }
        override suspend fun disposition(id: String, body: DispositionReq): CockpitLeadDto { dispositionReq = body; return lead }
        override suspend fun followUp(id: String, body: FollowUpReq): Map<String, Any?> { followUpReq = body; return emptyMap() }
        override suspend fun stages() = emptyList<PipelineStageDto>()
    }

    private class FakeDao : PipelineStageDao {
        override fun observe(): Flow<List<PipelineStageEntity>> = flowOf(emptyList())
        override suspend fun upsertAll(stages: List<PipelineStageEntity>) {}
    }

    private fun repo(api: FakeApi, session: SessionManager) = CockpitRepository(api, FakeDao(), session)

    @Test
    fun picked_disposition_goes_to_disposition_endpoint() = runTest {
        val api = FakeApi()
        val r = repo(api, mockk(relaxed = true))
        val res = r.submitDisposition("1", "Picked", "keen buyer", stageId = "stage-9")
        assertTrue(res.isSuccess)
        assertEquals("Picked", api.dispositionReq?.status)
        assertEquals("stage-9", api.dispositionReq?.custom_pipeline_stage_id)
        assertNull(api.followUpReq) // must NOT hit follow-up
    }

    @Test
    fun follow_up_outcome_goes_to_followup_endpoint() = runTest {
        val api = FakeApi()
        val r = repo(api, mockk(relaxed = true))
        val res = r.submitFollowUp("1", "Follow-up", "2026-07-27T10:00:00Z", "High", "call back", 30, false)
        assertTrue(res.isSuccess)
        assertEquals("Follow-up", api.followUpReq?.outcome)
        assertEquals(30, api.followUpReq?.reminder_minutes_before)
        assertNull(api.dispositionReq) // must NOT hit disposition
    }

    @Test
    fun call_without_telephony_config_is_blocked_before_the_network() = runTest {
        val api = FakeApi()
        val session = mockk<SessionManager>()
        coEvery { session.telephony() } returns TelephonyCreds(null, null, null)
        val res = repo(api, session).call("1")
        assertFalse(res.ok)
        assertFalse(api.callInvoked)                 // guarded — never reached the API
        assertTrue(res.message!!.contains("configured"))
    }

    @Test
    fun call_with_telephony_config_places_the_call() = runTest {
        val api = FakeApi()
        val session = mockk<SessionManager>()
        coEvery { session.telephony() } returns TelephonyCreds("k", null, "+91999")
        val res = repo(api, session).call("1")
        assertTrue(res.ok)
        assertTrue(api.callInvoked)
    }
}
