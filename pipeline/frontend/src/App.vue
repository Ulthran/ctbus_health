<template>
  <home-view v-if="!isAuthenticated" />
  <v-app v-else>
    <v-navigation-drawer v-model="drawer" temporary>
      <v-list nav density="compact" class="mt-2">
        <v-list-item
          prepend-icon="fas fa-bookmark"
          title="Recipes"
          :active="view === 'recipes'"
          active-color="green-darken-2"
          @click="view = 'recipes'; drawer = false"
        />
        <v-list-item
          prepend-icon="fas fa-chart-pie"
          title="Usage"
          :active="view === 'usage'"
          active-color="green-darken-2"
          @click="view = 'usage'; drawer = false"
        />
        <v-divider class="my-2" />
        <v-list-item
          prepend-icon="fas fa-right-from-bracket"
          title="Sign out"
          @click="signOut"
        />
      </v-list>
    </v-navigation-drawer>

    <v-app-bar color="green-darken-2" dark elevation="1">
      <v-btn icon variant="text" @click="drawer = !drawer">
        <v-icon icon="fas fa-bars" />
      </v-btn>
      <v-toolbar-title class="text-subtitle-1 font-weight-bold">
        <v-icon icon="fas fa-seedling" size="small" class="mr-1" />
        ctbus health
      </v-toolbar-title>
      <v-spacer />
      <div
        @click="view = 'day'"
        style="padding:0 14px;height:100%;display:flex;align-items:center;cursor:pointer;border-bottom:3px solid transparent;font-size:13px;font-weight:500;user-select:none"
        :style="isDayGroup ? 'border-color:rgba(255,255,255,0.85)' : ''"
      >
        <i class="fas fa-chart-bar" style="margin-right:5px;font-size:11px" />Day
      </div>
      <div
        @click="view = 'entry'"
        style="padding:0 14px;height:100%;display:flex;align-items:center;cursor:pointer;border-bottom:3px solid transparent;font-size:13px;font-weight:500;user-select:none"
        :style="view === 'entry' ? 'border-color:rgba(255,255,255,0.85)' : ''"
      >
        <i class="fas fa-plus-circle" style="margin-right:5px;font-size:11px" />Add
      </div>
    </v-app-bar>

    <v-main class="bg-grey-lighten-4">
      <div v-if="isDayGroup" style="background:white;border-bottom:1px solid #e0e0e0;display:flex;justify-content:center;padding:6px 0">
        <div style="display:inline-flex;border:1px solid #e0e0e0;border-radius:20px;overflow:hidden">
          <div
            v-for="sv in daySubviews"
            :key="sv.value"
            @click="view = sv.value"
            style="padding:5px 18px;cursor:pointer;font-size:12px;font-weight:500;user-select:none"
            :style="view === sv.value ? 'background:#2e7d32;color:white' : 'color:#757575'"
          >{{ sv.label }}</div>
        </div>
      </div>

      <dashboard-view v-if="view === 'day'" />
      <week-view v-else-if="view === 'week'" />
      <month-view v-else-if="view === 'month'" />
      <recipes-view v-else-if="view === 'recipes'" @use-recipe="onUseRecipe" />
      <usage-view v-else-if="view === 'usage'" />
      <entry-view v-else />
    </v-main>
  </v-app>
</template>

<script>
import { signOut } from '/src/auth.js';

export default {
  name: "App",
  props: {
    isAuthenticated: { type: Boolean, default: false },
  },
  data() {
    return {
      view: "day",
      drawer: false,
      daySubviews: [
        { value: "day",   label: "Day" },
        { value: "week",  label: "Week" },
        { value: "month", label: "Month" },
      ],
    };
  },
  computed: {
    isDayGroup() {
      return ["day", "week", "month"].includes(this.view);
    },
  },
  methods: {
    onUseRecipe(recipe) {
      window._ctbus_pending_recipe = recipe;
      this.view = "entry";
    },
    signOut,
  },
};
</script>
