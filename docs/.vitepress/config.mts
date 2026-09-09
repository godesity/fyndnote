import { defineConfig } from 'vitepress'
import { withMermaid } from 'vitepress-plugin-mermaid'

export default withMermaid(defineConfig({
  title: 'fyndnote',
  description: 'A general-purpose ML dataset annotation tool',
  base: '/fyndnote/',
  lang: 'en-US',

  // Pre-bundle fastdom for the dev server: mermaid's ESM chunks do a default
  // import of it, but fastdom 1.x ships only a UMD build with no ESM exports,
  // so served raw via @fs the browser throws "does not provide an export
  // named 'default'". Pre-bundling gives it proper default-export interop.
  vite: {
    optimizeDeps: {
      include: [
        'fastdom',
        'fastdom/extensions/fastdom-promised.js',
      ],
    },
  },

  // Centralized Mermaid styling — applies to every diagram, no per-diagram overrides.
  mermaid: {
    theme: 'base',
    // Brand colors for the light theme
    themeVariables: {
      primaryColor: '#fff7ed',          // sunset-50
      primaryTextColor: '#111827',      // text-heading
      primaryBorderColor: '#ea580c',    // sunset-600
      secondaryColor: '#ffe4e6',        // coral-100
      secondaryBorderColor: '#db2777',  // coral-600
      tertiaryColor: '#ede9fe',         // violet-100
      tertiaryBorderColor: '#7c3aed',   // violet-600
      lineColor: '#f97316',             // sunset-500
      fontSize: '14px',
    },
    // Injected CSS applies on any theme (including forced dark mode), so the
    // diagrams stay on-brand regardless of color mode.
    themeCSS: `
      .node rect, .node circle, .node ellipse, .node polygon, .node path,
      .cluster rect, .cluster circle, .cluster ellipse,
      #mermaid-svg .node rect, #mermaid-svg .node circle {
        fill: #fff7ed;
        stroke: #ea580c;
        stroke-width: 2px;
      }
      .nodeLabel, .edgeLabel, .clusterLabel, .node .label {
        color: #111827;
        font-family: system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
      }
      .edgeLabel {
        background: transparent;
        border: none;
        padding: 0;
      }
      .edgePath .path, .flowchart-link, #mermaid-svg .edgePath .path {
        stroke: #f97316;
        stroke-width: 2px;
      }
      .marker, .arrowheadPath, #mermaid-svg .marker {
        fill: #f97316;
      }
      /* Rounded edges for diagram boxes */
      .node rect, .node circle, .node ellipse, .node polygon, .node path,
      .cluster rect, .cluster circle, .cluster ellipse {
        border-radius: 10px;
      }
      .nodeLabel, .clusterLabel, .node .label {
        border-radius: 8px;
      }
    `,
  },

  themeConfig: {
    logo: '/favicon.svg',
    nav: [
      { text: 'Home', link: '/' },
      { text: 'Install', link: '/install' },
      { text: 'User Guide', link: '/guide/' },
      { text: 'API Reference', link: '/api/' },
      { text: 'Open the app', link: '/' },
    ],
    sidebar: {
      '/install/': [
        {
          text: 'Install',
          items: [
            { text: 'Docker Compose', link: '/install' },
            { text: 'Docker CLI', link: '/install' },
          ],
        },
      ],
      '/guide/': [
        {
          text: 'User Guide',
          items: [
            { text: 'Overview', link: '/guide/' },
            { text: 'Roles & Permissions', link: '/guide/roles' },
            { text: 'Admin: Create a Project', link: '/guide/create-project' },
            { text: 'Annotator: Label Rows', link: '/guide/annotating' },
            { text: 'Widgets & Templates', link: '/guide/widgets' },
            { text: 'Browse & Filters', link: '/guide/browsing' },
            { text: 'AI Prefill', link: '/guide/ai-prefill' },
            { text: 'Export', link: '/guide/export' },
          ],
        },
      ],
      '/api/': [
        {
          text: 'API Reference',
          items: [
            { text: 'Overview', link: '/api/' },
            { text: 'Interactive Swagger', link: '/api/swagger' },
          ],
        },
      ],
    },
    footer: {
      message: 'fyndnote — ML dataset annotation',
      copyright: 'MIT License',
    },
  },
}))
