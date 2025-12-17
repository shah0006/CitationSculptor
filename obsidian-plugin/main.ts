import {
  App,
  Editor,
  MarkdownView,
  Modal,
  Notice,
  Plugin,
  PluginSettingTab,
  Setting,
  requestUrl,
  TextComponent,
  DropdownComponent,
  ButtonComponent,
  TextAreaComponent,
} from "obsidian";

// ============================================================================
// Settings
// ============================================================================

interface CitationSculptorSettings {
  citationScriptPath: string;
  pythonPath: string;
  defaultFormat: "full" | "inline" | "endnote";
  autoCopyToClipboard: boolean;
  insertAtCursor: boolean;
  showAbstractInResults: boolean;
  maxSearchResults: number;
  recentLookups: RecentLookup[];
}

interface RecentLookup {
  identifier: string;
  inline_mark: string;
  timestamp: number;
}

const DEFAULT_SETTINGS: CitationSculptorSettings = {
  citationScriptPath: "/Users/tusharshah/Developer/MCP-Servers/CitationSculptor",
  pythonPath: "/Users/tusharshah/Developer/MCP-Servers/CitationSculptor/.venv/bin/python",
  defaultFormat: "full",
  autoCopyToClipboard: true,
  insertAtCursor: true,
  showAbstractInResults: false,
  maxSearchResults: 10,
  recentLookups: [],
};

// ============================================================================
// API Types
// ============================================================================

interface PubMedArticle {
  pmid: string;
  title: string;
  authors: string[];
  journal: string;
  year: string;
  doi?: string;
  abstract?: string;
}

interface CitationResult {
  success: boolean;
  identifier: string;
  identifier_type: string;
  inline_mark: string;
  endnote_citation: string;
  full_citation: string;
  metadata?: ArticleMetadata;
  error?: string;
}

interface ArticleMetadata {
  pmid?: string;
  title?: string;
  authors?: string[];
  journal?: string;
  journal_abbreviation?: string;
  year?: string;
  month?: string;
  volume?: string;
  issue?: string;
  pages?: string;
  doi?: string;
  abstract?: string;
}

// ============================================================================
// Main Citation Lookup Modal (Comprehensive)
// ============================================================================

class CitationLookupModal extends Modal {
  plugin: CitationSculptorPlugin;
  inputEl: TextComponent;
  formatDropdown: DropdownComponent;
  resultEl: HTMLElement;
  tabsEl: HTMLElement;
  searchResults: PubMedArticle[] = [];
  currentResult: CitationResult | null = null;
  activeTab: "lookup" | "search" | "batch" | "recent" = "lookup";

  constructor(app: App, plugin: CitationSculptorPlugin) {
    super(app);
    this.plugin = plugin;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.addClass("citation-sculptor-modal");
    contentEl.style.width = "700px";

    // Header
    const header = contentEl.createDiv({ cls: "cs-header" });
    header.createEl("h2", { text: "CitationSculptor" });

    // Tabs
    this.tabsEl = contentEl.createDiv({ cls: "cs-tabs" });
    this.createTabs();

    // Content area
    this.resultEl = contentEl.createDiv({ cls: "cs-content" });
    
    // Show initial tab
    this.showTab("lookup");
  }

  createTabs() {
    const tabs = [
      { id: "lookup", label: "Quick Lookup", icon: "🔍" },
      { id: "search", label: "PubMed Search", icon: "📚" },
      { id: "batch", label: "Batch Lookup", icon: "📋" },
      { id: "recent", label: "Recent", icon: "🕐" },
    ];

    tabs.forEach((tab) => {
      const tabEl = this.tabsEl.createEl("button", {
        cls: `cs-tab ${this.activeTab === tab.id ? "active" : ""}`,
        text: `${tab.icon} ${tab.label}`,
      });
      tabEl.dataset.tab = tab.id;
      tabEl.addEventListener("click", () => this.showTab(tab.id as any));
    });
  }

  showTab(tabId: "lookup" | "search" | "batch" | "recent") {
    this.activeTab = tabId;
    
    // Update tab styles
    this.tabsEl.querySelectorAll(".cs-tab").forEach((el) => {
      el.removeClass("active");
      if ((el as HTMLElement).dataset.tab === tabId) {
        el.addClass("active");
      }
    });

    this.resultEl.empty();

    switch (tabId) {
      case "lookup":
        this.renderLookupTab();
        break;
      case "search":
        this.renderSearchTab();
        break;
      case "batch":
        this.renderBatchTab();
        break;
      case "recent":
        this.renderRecentTab();
        break;
    }
  }

  // =========================================================================
  // Lookup Tab
  // =========================================================================

  renderLookupTab() {
    const container = this.resultEl.createDiv({ cls: "cs-lookup-tab" });

    container.createEl("p", {
      text: "Enter a PMID, DOI, PMC ID, or article title",
      cls: "cs-subtitle",
    });

    // Input row
    const inputRow = container.createDiv({ cls: "cs-input-row" });
    
    this.inputEl = new TextComponent(inputRow);
    this.inputEl.setPlaceholder("e.g., 37622666, 10.1093/eurheartj/ehad195, or article title");
    this.inputEl.inputEl.addClass("cs-main-input");
    this.inputEl.inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") this.doLookup();
    });

    // Format selector
    const formatRow = container.createDiv({ cls: "cs-format-row" });
    formatRow.createSpan({ text: "Format: " });
    
    this.formatDropdown = new DropdownComponent(formatRow);
    this.formatDropdown
      .addOption("full", "Full (inline + endnote)")
      .addOption("inline", "Inline only")
      .addOption("endnote", "Endnote only")
      .setValue(this.plugin.settings.defaultFormat);

    // Buttons
    const buttonRow = container.createDiv({ cls: "cs-button-row" });
    
    new ButtonComponent(buttonRow)
      .setButtonText("Look Up")
      .setCta()
      .onClick(() => this.doLookup());

    new ButtonComponent(buttonRow)
      .setButtonText("Look Up + Insert")
      .onClick(() => this.doLookupAndInsert());

    // Results area
    container.createDiv({ cls: "cs-results" });

    setTimeout(() => this.inputEl.inputEl.focus(), 50);
  }

  async doLookup() {
    const query = this.inputEl.getValue().trim();
    if (!query) {
      new Notice("Please enter an identifier");
      return;
    }

    const resultsEl = this.resultEl.querySelector(".cs-results") as HTMLElement;
    resultsEl.empty();
    resultsEl.createEl("p", { text: "Looking up...", cls: "cs-loading" });

    try {
      const result = await this.plugin.lookupCitation(query);
      this.currentResult = result;
      this.displayCitationResult(resultsEl, result);
      
      if (result.success) {
        this.plugin.addRecentLookup(query, result.inline_mark);
      }
    } catch (error) {
      resultsEl.empty();
      resultsEl.createEl("p", { text: `Error: ${error}`, cls: "cs-error" });
    }
  }

  async doLookupAndInsert() {
    await this.doLookup();
    if (this.currentResult?.success) {
      this.plugin.insertAtCursor(this.currentResult, this.formatDropdown.getValue() as any);
      this.close();
    }
  }

  // =========================================================================
  // Search Tab
  // =========================================================================

  renderSearchTab() {
    const container = this.resultEl.createDiv({ cls: "cs-search-tab" });

    container.createEl("p", {
      text: "Search PubMed for articles",
      cls: "cs-subtitle",
    });

    // Search input
    const inputRow = container.createDiv({ cls: "cs-input-row" });
    
    const searchInput = new TextComponent(inputRow);
    searchInput.setPlaceholder("e.g., ESC heart failure guidelines 2023");
    searchInput.inputEl.addClass("cs-main-input");
    searchInput.inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter") doSearch();
    });

    // Options row
    const optionsRow = container.createDiv({ cls: "cs-options-row" });
    optionsRow.createSpan({ text: "Max results: " });
    
    const maxResultsDropdown = new DropdownComponent(optionsRow);
    maxResultsDropdown
      .addOption("5", "5")
      .addOption("10", "10")
      .addOption("20", "20")
      .setValue(String(this.plugin.settings.maxSearchResults));

    // Buttons
    const buttonRow = container.createDiv({ cls: "cs-button-row" });
    
    new ButtonComponent(buttonRow)
      .setButtonText("Search PubMed")
      .setCta()
      .onClick(() => doSearch());

    // Results area
    const resultsEl = container.createDiv({ cls: "cs-results" });

    const doSearch = async () => {
      const query = searchInput.getValue().trim();
      if (!query) {
        new Notice("Please enter a search query");
        return;
      }

      resultsEl.empty();
      resultsEl.createEl("p", { text: "Searching PubMed...", cls: "cs-loading" });

      try {
        const maxResults = parseInt(maxResultsDropdown.getValue());
        this.searchResults = await this.plugin.searchPubMed(query, maxResults);
        this.displaySearchResults(resultsEl);
      } catch (error) {
        resultsEl.empty();
        resultsEl.createEl("p", { text: `Error: ${error}`, cls: "cs-error" });
      }
    };

    setTimeout(() => searchInput.inputEl.focus(), 50);
  }

  displaySearchResults(container: HTMLElement) {
    container.empty();

    if (this.searchResults.length === 0) {
      container.createEl("p", { text: "No results found", cls: "cs-no-results" });
      return;
    }

    container.createEl("h4", { text: `Found ${this.searchResults.length} results:` });

    const list = container.createDiv({ cls: "cs-search-list" });

    this.searchResults.forEach((article, index) => {
      const item = list.createDiv({ cls: "cs-search-item" });
      
      const titleRow = item.createDiv({ cls: "cs-search-title-row" });
      titleRow.createSpan({ text: `${index + 1}. `, cls: "cs-search-num" });
      titleRow.createSpan({ text: article.title, cls: "cs-search-title" });
      
      const metaEl = item.createDiv({ cls: "cs-search-meta" });
      const authors = article.authors.slice(0, 2).join(", ");
      metaEl.setText(`${authors}${article.authors.length > 2 ? " et al." : ""} • ${article.journal} (${article.year})`);
      
      const idRow = item.createDiv({ cls: "cs-search-ids" });
      idRow.createEl("code", { text: `PMID: ${article.pmid}` });
      if (article.doi) {
        idRow.createEl("code", { text: `DOI: ${article.doi}` });
      }

      // Action buttons
      const actions = item.createDiv({ cls: "cs-search-actions" });
      
      new ButtonComponent(actions)
        .setButtonText("Get Citation")
        .onClick(async () => {
          new Notice("Looking up citation...");
          const result = await this.plugin.lookupCitation(article.pmid);
          if (result.success) {
            this.currentResult = result;
            this.showTab("lookup");
            const resultsEl = this.resultEl.querySelector(".cs-results") as HTMLElement;
            if (resultsEl) {
              this.displayCitationResult(resultsEl, result);
            }
          } else {
            new Notice(`Error: ${result.error}`);
          }
        });

      new ButtonComponent(actions)
        .setButtonText("Insert")
        .setCta()
        .onClick(async () => {
          new Notice("Looking up and inserting...");
          const result = await this.plugin.lookupCitation(article.pmid);
          if (result.success) {
            this.plugin.insertAtCursor(result, this.plugin.settings.defaultFormat);
            this.close();
          } else {
            new Notice(`Error: ${result.error}`);
          }
        });

      if (this.plugin.settings.showAbstractInResults && article.abstract) {
        const abstractEl = item.createDiv({ cls: "cs-search-abstract" });
        abstractEl.createEl("strong", { text: "Abstract: " });
        abstractEl.createSpan({ text: article.abstract.substring(0, 300) + "..." });
      }
    });
  }

  // =========================================================================
  // Batch Tab
  // =========================================================================

  renderBatchTab() {
    const container = this.resultEl.createDiv({ cls: "cs-batch-tab" });

    container.createEl("p", {
      text: "Enter multiple identifiers (one per line)",
      cls: "cs-subtitle",
    });

    // Textarea
    const textareaEl = container.createEl("textarea", { cls: "cs-batch-input" });
    textareaEl.placeholder = "37622666\n10.1093/eurheartj/ehad195\nPMC7039045\n...";
    textareaEl.rows = 8;

    // Format selector
    const formatRow = container.createDiv({ cls: "cs-format-row" });
    formatRow.createSpan({ text: "Output format: " });
    
    const formatDropdown = new DropdownComponent(formatRow);
    formatDropdown
      .addOption("full", "Full citations")
      .addOption("inline", "Inline marks only")
      .addOption("endnote", "Endnotes only")
      .setValue(this.plugin.settings.defaultFormat);

    // Buttons
    const buttonRow = container.createDiv({ cls: "cs-button-row" });
    
    new ButtonComponent(buttonRow)
      .setButtonText("Process Batch")
      .setCta()
      .onClick(() => processBatch());

    new ButtonComponent(buttonRow)
      .setButtonText("Process & Insert All")
      .onClick(() => processBatchAndInsert());

    // Results area
    const resultsEl = container.createDiv({ cls: "cs-results" });

    const processBatch = async () => {
      const text = textareaEl.value.trim();
      if (!text) {
        new Notice("Please enter some identifiers");
        return;
      }

      const identifiers = text.split("\n").map((s) => s.trim()).filter((s) => s && !s.startsWith("#"));
      
      resultsEl.empty();
      resultsEl.createEl("p", { text: `Processing ${identifiers.length} identifiers...`, cls: "cs-loading" });

      const results: CitationResult[] = [];
      for (let i = 0; i < identifiers.length; i++) {
        try {
          const result = await this.plugin.lookupCitation(identifiers[i]);
          results.push(result);
          resultsEl.empty();
          resultsEl.createEl("p", { 
            text: `Processing ${i + 1}/${identifiers.length}...`, 
            cls: "cs-loading" 
          });
        } catch (error) {
          results.push({
            success: false,
            identifier: identifiers[i],
            identifier_type: "unknown",
            inline_mark: "",
            endnote_citation: "",
            full_citation: "",
            error: String(error),
          });
        }
      }

      displayBatchResults(results);
    };

    const processBatchAndInsert = async () => {
      await processBatch();
      // Insert all successful results
      const view = this.app.workspace.getActiveViewOfType(MarkdownView);
      if (!view) {
        new Notice("No active editor");
        return;
      }
      // Results are stored in closure, insert them
    };

    const displayBatchResults = (results: CitationResult[]) => {
      resultsEl.empty();

      const successCount = results.filter((r) => r.success).length;
      const failCount = results.length - successCount;

      resultsEl.createEl("h4", { 
        text: `Results: ${successCount} successful, ${failCount} failed` 
      });

      const format = formatDropdown.getValue();

      // Success section
      if (successCount > 0) {
        const successSection = resultsEl.createDiv({ cls: "cs-batch-section" });
        successSection.createEl("h5", { text: "✅ Successful" });
        
        const outputArea = successSection.createEl("textarea", { cls: "cs-batch-output" });
        outputArea.rows = 10;
        outputArea.readOnly = true;
        
        const successResults = results.filter((r) => r.success);
        let output = "";
        for (const r of successResults) {
          if (format === "inline") {
            output += r.inline_mark + "\n";
          } else if (format === "endnote") {
            output += r.full_citation + "\n\n";
          } else {
            output += `${r.inline_mark}\n${r.full_citation}\n\n`;
          }
        }
        outputArea.value = output;

        new ButtonComponent(successSection)
          .setButtonText("Copy All")
          .onClick(() => {
            navigator.clipboard.writeText(output);
            new Notice("Copied to clipboard!");
          });
      }

      // Failed section
      if (failCount > 0) {
        const failSection = resultsEl.createDiv({ cls: "cs-batch-section cs-batch-failed" });
        failSection.createEl("h5", { text: "❌ Failed" });
        
        const failList = failSection.createEl("ul");
        for (const r of results.filter((r) => !r.success)) {
          failList.createEl("li", { text: `${r.identifier}: ${r.error}` });
        }
      }
    };
  }

  // =========================================================================
  // Recent Tab
  // =========================================================================

  renderRecentTab() {
    const container = this.resultEl.createDiv({ cls: "cs-recent-tab" });

    const recent = this.plugin.settings.recentLookups;

    if (recent.length === 0) {
      container.createEl("p", { text: "No recent lookups", cls: "cs-no-results" });
      return;
    }

    container.createEl("h4", { text: `Recent Lookups (${recent.length})` });

    const list = container.createDiv({ cls: "cs-recent-list" });

    // Show most recent first
    [...recent].reverse().forEach((item) => {
      const row = list.createDiv({ cls: "cs-recent-item" });
      
      const infoEl = row.createDiv({ cls: "cs-recent-info" });
      infoEl.createEl("code", { text: item.inline_mark });
      infoEl.createEl("span", { 
        text: ` • ${new Date(item.timestamp).toLocaleDateString()}`,
        cls: "cs-recent-date"
      });

      const actions = row.createDiv({ cls: "cs-recent-actions" });
      
      new ButtonComponent(actions)
        .setButtonText("Copy")
        .onClick(() => {
          navigator.clipboard.writeText(item.inline_mark);
          new Notice("Copied!");
        });

      new ButtonComponent(actions)
        .setButtonText("Look Up Again")
        .onClick(async () => {
          const result = await this.plugin.lookupCitation(item.identifier);
          if (result.success) {
            this.currentResult = result;
            this.showTab("lookup");
            const resultsEl = this.resultEl.querySelector(".cs-results") as HTMLElement;
            if (resultsEl) {
              this.displayCitationResult(resultsEl, result);
            }
          }
        });

      new ButtonComponent(actions)
        .setButtonText("Insert")
        .setCta()
        .onClick(async () => {
          const result = await this.plugin.lookupCitation(item.identifier);
          if (result.success) {
            this.plugin.insertAtCursor(result, this.plugin.settings.defaultFormat);
            this.close();
          }
        });
    });

    // Clear button
    const clearRow = container.createDiv({ cls: "cs-clear-row" });
    new ButtonComponent(clearRow)
      .setButtonText("Clear History")
      .onClick(async () => {
        this.plugin.settings.recentLookups = [];
        await this.plugin.saveSettings();
        this.renderRecentTab();
        new Notice("History cleared");
      });
  }

  // =========================================================================
  // Display Citation Result
  // =========================================================================

  displayCitationResult(container: HTMLElement, result: CitationResult) {
    container.empty();

    if (!result.success) {
      container.createEl("p", { text: `Error: ${result.error}`, cls: "cs-error" });
      return;
    }

    // Inline mark section
    const inlineSection = container.createDiv({ cls: "cs-result-section" });
    inlineSection.createEl("h4", { text: "Inline Reference" });
    const inlineCode = inlineSection.createEl("code", { cls: "cs-inline-mark" });
    inlineCode.setText(result.inline_mark);
    
    new ButtonComponent(inlineSection)
      .setButtonText("Copy")
      .onClick(() => {
        navigator.clipboard.writeText(result.inline_mark);
        new Notice("Inline reference copied!");
      });

    // Full citation section
    const fullSection = container.createDiv({ cls: "cs-result-section" });
    fullSection.createEl("h4", { text: "Full Citation" });
    const fullText = fullSection.createDiv({ cls: "cs-full-citation" });
    fullText.setText(result.full_citation);
    
    new ButtonComponent(fullSection)
      .setButtonText("Copy")
      .onClick(() => {
        navigator.clipboard.writeText(result.full_citation);
        new Notice("Full citation copied!");
      });

    // Metadata section (collapsible)
    if (result.metadata) {
      const metaSection = container.createDiv({ cls: "cs-result-section cs-metadata-section" });
      const metaHeader = metaSection.createDiv({ cls: "cs-metadata-header" });
      metaHeader.createEl("h4", { text: "📊 Metadata" });
      
      const metaContent = metaSection.createDiv({ cls: "cs-metadata-content" });
      metaContent.style.display = "none";
      
      metaHeader.addEventListener("click", () => {
        metaContent.style.display = metaContent.style.display === "none" ? "block" : "none";
      });

      const meta = result.metadata;
      const table = metaContent.createEl("table", { cls: "cs-metadata-table" });
      
      const fields = [
        ["Title", meta.title],
        ["Authors", meta.authors?.join(", ")],
        ["Journal", meta.journal_abbreviation || meta.journal],
        ["Year", meta.year],
        ["Volume/Issue", `${meta.volume || ""}${meta.issue ? `(${meta.issue})` : ""}`],
        ["Pages", meta.pages],
        ["PMID", meta.pmid],
        ["DOI", meta.doi],
      ];

      for (const [label, value] of fields) {
        if (value) {
          const row = table.createEl("tr");
          row.createEl("th", { text: label });
          row.createEl("td", { text: String(value) });
        }
      }

      // Abstract
      if (meta.abstract) {
        metaContent.createEl("h5", { text: "Abstract" });
        metaContent.createEl("p", { text: meta.abstract, cls: "cs-abstract" });
      }
    }

    // Action buttons
    const actions = container.createDiv({ cls: "cs-actions" });
    
    new ButtonComponent(actions)
      .setButtonText("Insert Inline Only")
      .onClick(() => {
        this.plugin.insertAtCursor(result, "inline");
        this.close();
      });

    new ButtonComponent(actions)
      .setButtonText("Insert Full Citation")
      .onClick(() => {
        this.plugin.insertAtCursor(result, "endnote");
        this.close();
      });

    new ButtonComponent(actions)
      .setButtonText("Insert Both")
      .setCta()
      .onClick(() => {
        this.plugin.insertAtCursor(result, "full");
        this.close();
      });
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}

// ============================================================================
// Quick Lookup Modal (Simple)
// ============================================================================

class QuickLookupModal extends Modal {
  plugin: CitationSculptorPlugin;
  onSubmit: (result: CitationResult) => void;

  constructor(app: App, plugin: CitationSculptorPlugin, onSubmit: (result: CitationResult) => void) {
    super(app);
    this.plugin = plugin;
    this.onSubmit = onSubmit;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.createEl("h3", { text: "Quick Citation Lookup" });

    new Setting(contentEl)
      .setName("Identifier")
      .setDesc("PMID, DOI, PMC ID, or title")
      .addText((text) => {
        text.setPlaceholder("e.g., 37622666");
        text.inputEl.style.width = "300px";
        text.inputEl.addEventListener("keydown", async (e) => {
          if (e.key === "Enter") {
            const query = text.getValue().trim();
            if (query) {
              new Notice("Looking up citation...");
              try {
                const result = await this.plugin.lookupCitation(query);
                this.onSubmit(result);
                this.close();
              } catch (error) {
                new Notice(`Error: ${error}`);
              }
            }
          }
        });
        setTimeout(() => text.inputEl.focus(), 50);
      });
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}

// ============================================================================
// Abstract Modal
// ============================================================================

class AbstractModal extends Modal {
  title: string;
  abstract: string;

  constructor(app: App, title: string, abstract: string) {
    super(app);
    this.title = title;
    this.abstract = abstract;
  }

  onOpen() {
    const { contentEl } = this;
    contentEl.createEl("h2", { text: this.title });
    contentEl.createEl("p", { text: this.abstract, cls: "cs-abstract-full" });
    
    new ButtonComponent(contentEl)
      .setButtonText("Copy Abstract")
      .onClick(() => {
        navigator.clipboard.writeText(this.abstract);
        new Notice("Abstract copied!");
      });
  }

  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
}

// ============================================================================
// Settings Tab
// ============================================================================

class CitationSculptorSettingTab extends PluginSettingTab {
  plugin: CitationSculptorPlugin;

  constructor(app: App, plugin: CitationSculptorPlugin) {
    super(app, plugin);
    this.plugin = plugin;
  }

  display(): void {
    const { containerEl } = this;
    containerEl.empty();

    containerEl.createEl("h2", { text: "CitationSculptor Settings" });

    // Paths section
    containerEl.createEl("h3", { text: "Paths" });

    new Setting(containerEl)
      .setName("CitationSculptor Path")
      .setDesc("Path to the CitationSculptor directory")
      .addText((text) =>
        text
          .setPlaceholder("/path/to/CitationSculptor")
          .setValue(this.plugin.settings.citationScriptPath)
          .onChange(async (value) => {
            this.plugin.settings.citationScriptPath = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Python Path")
      .setDesc("Path to the Python executable in the venv")
      .addText((text) =>
        text
          .setPlaceholder("/path/to/.venv/bin/python")
          .setValue(this.plugin.settings.pythonPath)
          .onChange(async (value) => {
            this.plugin.settings.pythonPath = value;
            await this.plugin.saveSettings();
          })
      );

    // Behavior section
    containerEl.createEl("h3", { text: "Behavior" });

    new Setting(containerEl)
      .setName("Default Format")
      .setDesc("Default citation format when inserting")
      .addDropdown((dropdown) =>
        dropdown
          .addOption("full", "Full (inline + endnote)")
          .addOption("inline", "Inline only")
          .addOption("endnote", "Endnote only")
          .setValue(this.plugin.settings.defaultFormat)
          .onChange(async (value: "full" | "inline" | "endnote") => {
            this.plugin.settings.defaultFormat = value;
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Auto Copy to Clipboard")
      .setDesc("Automatically copy citations to clipboard when inserted")
      .addToggle((toggle) =>
        toggle.setValue(this.plugin.settings.autoCopyToClipboard).onChange(async (value) => {
          this.plugin.settings.autoCopyToClipboard = value;
          await this.plugin.saveSettings();
        })
      );

    new Setting(containerEl)
      .setName("Insert at Cursor")
      .setDesc("Automatically insert citation at cursor position")
      .addToggle((toggle) =>
        toggle.setValue(this.plugin.settings.insertAtCursor).onChange(async (value) => {
          this.plugin.settings.insertAtCursor = value;
          await this.plugin.saveSettings();
        })
      );

    // Search section
    containerEl.createEl("h3", { text: "Search" });

    new Setting(containerEl)
      .setName("Max Search Results")
      .setDesc("Maximum number of PubMed search results to show")
      .addDropdown((dropdown) =>
        dropdown
          .addOption("5", "5")
          .addOption("10", "10")
          .addOption("20", "20")
          .addOption("50", "50")
          .setValue(String(this.plugin.settings.maxSearchResults))
          .onChange(async (value) => {
            this.plugin.settings.maxSearchResults = parseInt(value);
            await this.plugin.saveSettings();
          })
      );

    new Setting(containerEl)
      .setName("Show Abstracts in Search Results")
      .setDesc("Display article abstracts in search results (slower)")
      .addToggle((toggle) =>
        toggle.setValue(this.plugin.settings.showAbstractInResults).onChange(async (value) => {
          this.plugin.settings.showAbstractInResults = value;
          await this.plugin.saveSettings();
        })
      );

    // Cache section
    containerEl.createEl("h3", { text: "Cache & History" });

    new Setting(containerEl)
      .setName("Recent Lookups")
      .setDesc(`${this.plugin.settings.recentLookups.length} items in history`)
      .addButton((button) =>
        button.setButtonText("Clear History").onClick(async () => {
          this.plugin.settings.recentLookups = [];
          await this.plugin.saveSettings();
          this.display();
          new Notice("History cleared");
        })
      );

    new Setting(containerEl)
      .setName("Test Connection")
      .setDesc("Test connection to CitationSculptor")
      .addButton((button) =>
        button.setButtonText("Test").onClick(async () => {
          new Notice("Testing connection...");
          try {
            const result = await this.plugin.lookupCitation("32089132");
            if (result.success) {
              new Notice("✅ Connection successful!");
            } else {
              new Notice(`❌ Error: ${result.error}`);
            }
          } catch (error) {
            new Notice(`❌ Error: ${error}`);
          }
        })
      );
  }
}

// ============================================================================
// Main Plugin
// ============================================================================

export default class CitationSculptorPlugin extends Plugin {
  settings: CitationSculptorSettings;

  async onload() {
    await this.loadSettings();

    // Add ribbon icon
    this.addRibbonIcon("quote-glyph", "CitationSculptor", () => {
      new CitationLookupModal(this.app, this).open();
    });

    // Main command - Open full modal
    this.addCommand({
      id: "open-citation-lookup",
      name: "Open Citation Lookup",
      callback: () => {
        new CitationLookupModal(this.app, this).open();
      },
    });

    // Quick lookup command
    this.addCommand({
      id: "quick-lookup",
      name: "Quick Lookup (PMID/DOI/Title)",
      editorCallback: (editor: Editor, view: MarkdownView) => {
        new QuickLookupModal(this.app, this, (result) => {
          if (result.success) {
            this.insertCitationInEditor(editor, result, this.settings.defaultFormat);
          } else {
            new Notice(`Error: ${result.error}`);
          }
        }).open();
      },
    });

    // Look up selection
    this.addCommand({
      id: "lookup-selection",
      name: "Look Up Selected Text",
      editorCallback: async (editor: Editor, view: MarkdownView) => {
        const selection = editor.getSelection().trim();
        if (!selection) {
          new Notice("Please select text to look up");
          return;
        }
        new Notice("Looking up citation...");
        try {
          const result = await this.lookupCitation(selection);
          if (result.success) {
            this.insertCitationInEditor(editor, result, this.settings.defaultFormat);
          } else {
            new Notice(`Error: ${result.error}`);
          }
        } catch (error) {
          new Notice(`Error: ${error}`);
        }
      },
    });

    // Insert inline only
    this.addCommand({
      id: "quick-lookup-inline",
      name: "Quick Lookup (Insert Inline Only)",
      editorCallback: (editor: Editor, view: MarkdownView) => {
        new QuickLookupModal(this.app, this, (result) => {
          if (result.success) {
            editor.replaceSelection(result.inline_mark);
            if (this.settings.autoCopyToClipboard) {
              navigator.clipboard.writeText(result.inline_mark);
            }
            new Notice("Inline reference inserted!");
          } else {
            new Notice(`Error: ${result.error}`);
          }
        }).open();
      },
    });

    // Search PubMed command
    this.addCommand({
      id: "search-pubmed",
      name: "Search PubMed",
      callback: () => {
        const modal = new CitationLookupModal(this.app, this);
        modal.open();
        // Switch to search tab after opening
        setTimeout(() => modal.showTab("search"), 100);
      },
    });

    // Batch lookup command
    this.addCommand({
      id: "batch-lookup",
      name: "Batch Citation Lookup",
      callback: () => {
        const modal = new CitationLookupModal(this.app, this);
        modal.open();
        setTimeout(() => modal.showTab("batch"), 100);
      },
    });

    // Recent lookups command
    this.addCommand({
      id: "recent-lookups",
      name: "Recent Citation Lookups",
      callback: () => {
        const modal = new CitationLookupModal(this.app, this);
        modal.open();
        setTimeout(() => modal.showTab("recent"), 100);
      },
    });

    // Add settings tab
    this.addSettingTab(new CitationSculptorSettingTab(this.app, this));
  }

  onunload() {}

  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }

  async saveSettings() {
    await this.saveData(this.settings);
  }

  addRecentLookup(identifier: string, inline_mark: string) {
    // Remove if already exists
    this.settings.recentLookups = this.settings.recentLookups.filter(
      (r) => r.identifier !== identifier
    );
    
    // Add to front
    this.settings.recentLookups.push({
      identifier,
      inline_mark,
      timestamp: Date.now(),
    });
    
    // Keep only last 50
    if (this.settings.recentLookups.length > 50) {
      this.settings.recentLookups = this.settings.recentLookups.slice(-50);
    }
    
    this.saveSettings();
  }

  // =========================================================================
  // Citation Lookup via CLI
  // =========================================================================

  async lookupCitation(identifier: string): Promise<CitationResult> {
    const { exec } = require("child_process");
    const { promisify } = require("util");
    const execAsync = promisify(exec);

    const cmd = `cd "${this.settings.citationScriptPath}" && "${this.settings.pythonPath}" citation_lookup.py --auto "${identifier}" -f json`;

    try {
      const { stdout, stderr } = await execAsync(cmd, { maxBuffer: 1024 * 1024 });
      const result = JSON.parse(stdout);
      return {
        success: result.success,
        identifier: result.identifier || identifier,
        identifier_type: result.identifier_type || "unknown",
        inline_mark: result.inline_mark || "",
        endnote_citation: result.endnote_citation || result.full_citation || "",
        full_citation: result.full_citation || "",
        metadata: result.metadata,
        error: result.error,
      };
    } catch (error: any) {
      return {
        success: false,
        identifier: identifier,
        identifier_type: "unknown",
        inline_mark: "",
        endnote_citation: "",
        full_citation: "",
        error: error.message || "Unknown error",
      };
    }
  }

  async searchPubMed(query: string, maxResults: number = 10): Promise<PubMedArticle[]> {
    const baseUrl = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils";
    const searchUrl = `${baseUrl}/esearch.fcgi?db=pubmed&term=${encodeURIComponent(query)}&retmax=${maxResults}&retmode=json`;

    try {
      const searchResponse = await requestUrl({ url: searchUrl });
      const searchData = searchResponse.json;
      const pmids = searchData.esearchresult?.idlist || [];

      if (pmids.length === 0) return [];

      const summaryUrl = `${baseUrl}/esummary.fcgi?db=pubmed&id=${pmids.join(",")}&retmode=json`;
      const summaryResponse = await requestUrl({ url: summaryUrl });
      const summaryData = summaryResponse.json;

      const articles: PubMedArticle[] = [];
      for (const pmid of pmids) {
        const doc = summaryData.result?.[pmid];
        if (doc) {
          articles.push({
            pmid: pmid,
            title: doc.title || "Unknown",
            authors: (doc.authors || []).map((a: any) => a.name),
            journal: doc.source || "Unknown",
            year: doc.pubdate?.split(" ")[0] || "",
            doi: doc.elocationid?.replace("doi: ", "") || "",
          });
        }
      }
      return articles;
    } catch (error) {
      console.error("PubMed search error:", error);
      return [];
    }
  }

  insertAtCursor(result: CitationResult, format: "full" | "inline" | "endnote" = "full") {
    const view = this.app.workspace.getActiveViewOfType(MarkdownView);
    if (view) {
      this.insertCitationInEditor(view.editor, result, format);
    }
  }

  insertCitationInEditor(editor: Editor, result: CitationResult, format: "full" | "inline" | "endnote") {
    const cursor = editor.getCursor();
    
    if (format === "inline") {
      editor.replaceSelection(result.inline_mark);
      if (this.settings.autoCopyToClipboard) {
        navigator.clipboard.writeText(result.inline_mark);
      }
      new Notice("Inline reference inserted!");
      return;
    }

    if (format === "endnote") {
      // Just insert the full citation at cursor
      editor.replaceSelection(result.full_citation);
      if (this.settings.autoCopyToClipboard) {
        navigator.clipboard.writeText(result.full_citation);
      }
      new Notice("Citation inserted!");
      return;
    }

    // Full format: insert inline at cursor, add endnote to References
    editor.replaceSelection(result.inline_mark);
    
    const doc = editor.getValue();
    
    // Check if endnote already exists
    if (!doc.includes(result.full_citation)) {
      // Find or create References section
      const refMatch = doc.match(/^##?\s*(References|Sources|Citations|Bibliography)/im);
      
      if (refMatch) {
        const refIndex = doc.indexOf(refMatch[0]) + refMatch[0].length;
        const before = doc.substring(0, refIndex);
        const after = doc.substring(refIndex);
        editor.setValue(before + "\n\n" + result.full_citation + after);
      } else {
        editor.setValue(doc + "\n\n## References\n\n" + result.full_citation);
      }
    }

    if (this.settings.autoCopyToClipboard) {
      navigator.clipboard.writeText(result.full_citation);
    }
    
    new Notice("Citation inserted!");
  }
}
