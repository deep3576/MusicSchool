package com.musicschool.shared.repository

import com.musicschool.shared.api.MusicSchoolApi
import com.musicschool.shared.model.AvailabilitySlot
import com.musicschool.shared.model.BookingSummary
import com.musicschool.shared.model.LoginRequest
import com.musicschool.shared.model.UserSummary

class AppRepository(private val api: MusicSchoolApi) {
    suspend fun login(email: String, password: String): UserSummary = api.login(LoginRequest(email, password))
    suspend fun me(): UserSummary = api.me()

    suspend fun loadStudentAvailability(startIso: String, endIso: String): List<AvailabilitySlot> =
        api.studentAvailability(startIso, endIso)

    suspend fun loadStudentBookings(): List<BookingSummary> = api.studentBookings()
    suspend fun createBooking(availabilityId: Int): Int = api.createStudentBooking(availabilityId)

    suspend fun loadTeacherBookings(): List<BookingSummary> = api.teacherBookings()
    suspend fun markPresent(bookingId: Int) = api.teacherSetPresent(bookingId)
    suspend fun markAbsent(bookingId: Int) = api.teacherSetAbsent(bookingId)

    suspend fun loadAdminBookings(): List<BookingSummary> = api.adminBookings()
    suspend fun cancelAdminBooking(bookingId: Int) = api.adminCancelBooking(bookingId)
}
