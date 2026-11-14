package org.modstride.examples.counter;

import com.mojang.serialization.DynamicOps;
import net.minecraft.SharedConstants;
import net.minecraft.nbt.NbtOps;
import net.minecraft.nbt.Tag;
import net.minecraft.server.Bootstrap;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.item.Items;

public final class CounterParity {
    public static void main(String[] args) {
        SharedConstants.tryDetectVersion();
        Bootstrap.bootStrap();

        ItemStack stack = new ItemStack(Items.CLOCK);
        require("new", CounterStorage.read(stack), 0);
        require("first-use", FieldCounter.increment(stack), 1);
        require("second-use", FieldCounter.increment(stack), 2);
        require("independent-stack", CounterStorage.read(new ItemStack(Items.CLOCK)), 0);
        require("copy", CounterStorage.read(stack.copy()), 2);

        DynamicOps<Tag> ops = NbtOps.INSTANCE;
        Tag encoded = ItemStack.CODEC.encodeStart(ops, stack).result().orElseThrow();
        ItemStack reloaded = ItemStack.CODEC.parse(ops, encoded).result().orElseThrow();
        require("reload", CounterStorage.read(reloaded), 2);
        require("use-after-reload", FieldCounter.increment(reloaded), 3);
    }

    private static void require(String scenario, int actual, int expected) {
        if (actual != expected) {
            throw new AssertionError(scenario + ": expected " + expected + ", got " + actual);
        }
        System.out.println("MODSTRIDE_OBSERVATION " + scenario + "=" + actual);
    }
}
