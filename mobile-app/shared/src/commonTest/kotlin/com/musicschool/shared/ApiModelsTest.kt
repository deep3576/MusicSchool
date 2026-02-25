package com.musicschool.shared

import com.musicschool.shared.model.UserSummary
import kotlin.test.Test
import kotlin.test.assertEquals

class ApiModelsTest {
    @Test
    fun userSummary_defaults_are_stable() {
        val u = UserSummary(id = 1, email = "a@b.com")
        assertEquals(1, u.id)
        assertEquals("a@b.com", u.email)
        assertEquals(emptyList(), u.roles)
    }
}
