<template>
  <v-container class="py-6" style="max-width:600px">

    <div class="d-flex align-center justify-space-between mb-4">
      <div class="text-h6 font-weight-bold">API Usage</div>
      <div class="d-flex align-center gap-2">
        <v-btn icon variant="text" size="small" :disabled="loading" @click="prevMonth">
          <v-icon icon="fas fa-chevron-left" size="x-small" />
        </v-btn>
        <span class="text-body-2" style="min-width:72px;text-align:center">{{ monthLabel }}</span>
        <v-btn icon variant="text" size="small" :disabled="loading || selectedMonth >= currentMonth" @click="nextMonth">
          <v-icon icon="fas fa-chevron-right" size="x-small" />
        </v-btn>
      </div>
    </div>

    <div v-if="loading" class="text-center py-12">
      <v-progress-circular indeterminate color="green-darken-2" size="48" />
    </div>

    <template v-else>
      <v-card rounded="lg" elevation="1" class="mb-3">
        <v-card-text class="pa-0">
          <div
            v-for="(stat, idx) in stats"
            :key="stat.key"
            class="d-flex align-center px-4 py-3"
            :style="idx < stats.length - 1 ? 'border-bottom:1px solid #f5f5f5' : ''"
          >
            <div class="mr-3 d-flex align-center justify-center" style="width:36px;height:36px;border-radius:50%;background:#f5f5f5">
              <i :class="stat.icon" :style="{ fontSize: '15px', color: stat.color }" />
            </div>
            <div class="flex-grow-1">
              <div class="text-body-2 font-weight-medium">{{ stat.label }}</div>
              <div class="text-caption text-grey">{{ stat.desc }}</div>
            </div>
            <div class="text-right">
              <div class="text-h6" :style="{ color: usage[stat.key] ? stat.color : '#bdbdbd' }">
                {{ usage[stat.key] || 0 }}
              </div>
              <div class="text-caption text-grey">calls</div>
            </div>
          </div>
        </v-card-text>
      </v-card>

      <div class="text-caption text-grey text-center">
        <template v-if="usage.updated_at">Last updated: {{ formatTime(usage.updated_at) }}</template>
        <template v-else>No usage data recorded yet this month</template>
      </div>
    </template>

  </v-container>
</template>

<script>
const MONTHS_SHORT = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];

function s3Base() {
  const v = (typeof window !== "undefined" && window.CTBUS_S3) || "";
  return v === "CTBUS_S3_PLACEHOLDER" ? "" : v;
}

function toMonthStr(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
}

export default {
  name: "UsageView",
  data() {
    const now = new Date();
    return {
      selectedMonth: toMonthStr(now),
      currentMonth: toMonthStr(now),
      usage: {},
      loading: true,
      stats: [
        { key: "bedrock_calls",      label: "Claude / Bedrock",    desc: "AI food parsing & restaurant extraction calls", icon: "fas fa-brain",    color: "#ff6b2b" },
        { key: "tavily_calls",       label: "Tavily Search",       desc: "Restaurant menu web search calls",              icon: "fas fa-search",   color: "#2196F3" },
        { key: "usda_calls",         label: "USDA FoodData",       desc: "Nutrition database search queries",             icon: "fas fa-database", color: "#4CAF50" },
        { key: "off_lookups",        label: "Open Food Facts",     desc: "Barcode scan lookups (from browser)",           icon: "fas fa-barcode",  color: "#9C27B0" },
      ],
    };
  },
  computed: {
    monthLabel() {
      const [y, m] = this.selectedMonth.split("-").map(Number);
      return `${MONTHS_SHORT[m - 1]} ${y}`;
    },
  },
  async created() {
    await this.loadUsage();
  },
  methods: {
    async loadUsage() {
      this.loading = true;
      this.usage = {};
      try {
        const resp = await fetch(`${s3Base()}/diet/usage/${this.selectedMonth}.json`);
        if (resp.ok) this.usage = await resp.json();
      } catch (e) { /* no data yet */ }
      finally { this.loading = false; }
    },
    prevMonth() {
      const [y, m] = this.selectedMonth.split("-").map(Number);
      const d = new Date(y, m - 2, 1);
      this.selectedMonth = toMonthStr(d);
      this.loadUsage();
    },
    nextMonth() {
      const [y, m] = this.selectedMonth.split("-").map(Number);
      const d = new Date(y, m, 1);
      const next = toMonthStr(d);
      if (next <= this.currentMonth) {
        this.selectedMonth = next;
        this.loadUsage();
      }
    },
    formatTime(iso) {
      if (!iso) return "";
      const d = new Date(iso);
      return d.toLocaleString();
    },
  },
};
</script>
