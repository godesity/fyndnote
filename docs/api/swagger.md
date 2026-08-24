---
layout: false
---

<script setup>
import { ApiReference } from '@scalar/api-reference'
import '@scalar/api-reference/style.css'
import '@scalar/api-reference/vue-styles.css'
import openapi from '../public/openapi.json'
</script>

<div style="height: 100vh; overflow: auto;">
  <ApiReference :configuration="{ content: openapi }" />
</div>
