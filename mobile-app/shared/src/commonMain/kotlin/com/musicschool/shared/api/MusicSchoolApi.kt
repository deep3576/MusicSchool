package com.musicschool.shared.api

import com.musicschool.shared.model.AvailabilitySlot
import com.musicschool.shared.model.BookingSummary
import com.musicschool.shared.model.LoginRequest
import com.musicschool.shared.model.RoleRequest
import com.musicschool.shared.model.UserSummary

interface MusicSchoolApi {
    suspend fun login(request: LoginRequest): UserSummary
    suspend fun me(): UserSummary
    suspend fun selectRole(request: RoleRequest)

    suspend fun studentAvailability(startIso: String, endIso: String): List<AvailabilitySlot>
    suspend fun studentBookings(): List<BookingSummary>
    suspend fun createStudentBooking(availabilityId: Int): Int

    suspend fun teacherBookings(): List<BookingSummary>
    suspend fun teacherSetPresent(bookingId: Int)
    suspend fun teacherSetAbsent(bookingId: Int)

    suspend fun adminBookings(): List<BookingSummary>
    suspend fun adminCancelBooking(bookingId: Int)
}
