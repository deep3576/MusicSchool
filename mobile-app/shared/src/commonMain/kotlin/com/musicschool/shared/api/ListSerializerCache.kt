package com.musicschool.shared.api

import com.musicschool.shared.model.AvailabilitySlot
import com.musicschool.shared.model.BookingSummary
import kotlinx.serialization.builtins.ListSerializer

object ListSerializerCache {
    val availabilityList = ListSerializer(AvailabilitySlot.serializer())
    val bookingList = ListSerializer(BookingSummary.serializer())
}
