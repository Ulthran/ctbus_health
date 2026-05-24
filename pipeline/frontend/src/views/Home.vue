<template>
  <v-app>
    <v-main class="bg-grey-lighten-4">
      <div style="min-height:100vh;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:24px">
        <div style="max-width:480px;width:100%;text-align:center">
          <v-icon icon="fas fa-seedling" size="64" color="green-darken-2" class="mb-4" />
          <h1 class="text-h5 font-weight-bold mb-2" style="color:#2e7d32">ctbus health</h1>
          <p class="text-body-1 text-medium-emphasis mb-6">
            A personal health tracker for logging meals, tracking nutrition, and
            reviewing trends — built around a quick Telegram-style entry flow.
          </p>
          <v-btn
            color="green-darken-2"
            size="large"
            variant="elevated"
            block
            @click="signIn"
            style="min-height:52px;font-size:16px"
          >
            <v-icon icon="fab fa-google" class="mr-2" />
            Sign in with Google
          </v-btn>
          <p class="text-caption text-disabled mt-4">
            Access is by invitation only.
          </p>
        </div>
      </div>
    </v-main>
  </v-app>
</template>

<script>
import { redirectToLogin } from '/src/auth.js';

export default {
  name: 'HomeView',
  methods: {
    signIn() {
      redirectToLogin();
    },
  },
};
</script>
