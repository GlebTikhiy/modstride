package org.modstride.examples.counter;

import net.minecraft.nbt.CompoundTag;
import net.minecraft.world.item.ItemStack;

final class CounterStorage {
    private static final String KEY = "modstride_counter:count";

    static int read(ItemStack stack) {
        CompoundTag tag = stack.getTag();
        return tag == null ? 0 : tag.getInt(KEY);
    }

    static void write(ItemStack stack, int count) {
        stack.getOrCreateTag().putInt(KEY, count);
    }
}
