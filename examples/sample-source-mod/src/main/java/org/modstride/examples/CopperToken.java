package org.modstride.examples;

import net.fabricmc.api.ModInitializer;
import net.minecraft.core.Registry;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.item.Item;

public final class CopperToken implements ModInitializer {
    @Override
    public void onInitialize() {
        Registry.register(
            BuiltInRegistries.ITEM,
            new ResourceLocation("modstride_example", "copper_token"),
            new Item(new Item.Properties().stacksTo(16))
        );
    }
}
