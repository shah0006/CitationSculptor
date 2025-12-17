/*
CitationSculptor Obsidian Plugin
*/
var __defProp = Object.defineProperty;
var __getOwnPropDesc = Object.getOwnPropertyDescriptor;
var __getOwnPropNames = Object.getOwnPropertyNames;
var __hasOwnProp = Object.prototype.hasOwnProperty;
var __export = (target, all) => {
  for (var name in all)
    __defProp(target, name, { get: all[name], enumerable: true });
};
var __copyProps = (to, from, except, desc) => {
  if (from && typeof from === "object" || typeof from === "function") {
    for (let key of __getOwnPropNames(from))
      if (!__hasOwnProp.call(to, key) && key !== except)
        __defProp(to, key, { get: () => from[key], enumerable: !(desc = __getOwnPropDesc(from, key)) || desc.enumerable });
  }
  return to;
};
var __toCommonJS = (mod) => __copyProps(__defProp({}, "__esModule", { value: true }), mod);

// main.ts
var main_exports = {};
__export(main_exports, {
  default: () => CitationSculptorPlugin
});
module.exports = __toCommonJS(main_exports);
var import_obsidian = require("obsidian");
var DEFAULT_SETTINGS = {
  citationScriptPath: "/Users/tusharshah/Developer/MCP-Servers/CitationSculptor",
  pythonPath: "/Users/tusharshah/Developer/MCP-Servers/CitationSculptor/.venv/bin/python",
  defaultFormat: "full",
  citationStyle: "vancouver",
  autoCopyToClipboard: true,
  insertAtCursor: true,
  showAbstractInResults: false,
  maxSearchResults: 10,
  recentLookups: [],
  // HTTP API settings (preferred for efficiency)
  useHttpApi: true,
  httpApiUrl: "http://127.0.0.1:3019",
  // Safety settings
  createBackupBeforeProcessing: true,
  lastBackupPath: "",
  // Server sync settings
  syncWithServer: true,
  lastServerSync: "",
  syncIntervalSeconds: 30,
  // Check for changes every 30 seconds
  lastKnownServerModified: ""
};
var CitationLookupModal = class extends import_obsidian.Modal {
  constructor(app, plugin) {
    super(app);
    this.searchResults = [];
    this.currentResult = null;
    this.activeTab = "lookup";
    this.plugin = plugin;
  }
  onOpen() {
    const { contentEl } = this;
    contentEl.empty();
    contentEl.addClass("citation-sculptor-modal");
    contentEl.style.width = "700px";
    const header = contentEl.createDiv({ cls: "cs-header" });
    header.createEl("h2", { text: "CitationSculptor" });
    this.tabsEl = contentEl.createDiv({ cls: "cs-tabs" });
    this.createTabs();
    this.resultEl = contentEl.createDiv({ cls: "cs-content" });
    this.showTab("lookup");
  }
  createTabs() {
    const tabs = [
      { id: "lookup", label: "Quick Lookup", icon: "\u{1F50D}" },
      { id: "search", label: "PubMed Search", icon: "\u{1F4DA}" },
      { id: "batch", label: "Batch Lookup", icon: "\u{1F4CB}" },
      { id: "recent", label: "Recent", icon: "\u{1F550}" }
    ];
    tabs.forEach((tab) => {
      const tabEl = this.tabsEl.createEl("button", {
        cls: `cs-tab ${this.activeTab === tab.id ? "active" : ""}`,
        text: `${tab.icon} ${tab.label}`
      });
      tabEl.dataset.tab = tab.id;
      tabEl.addEventListener("click", () => this.showTab(tab.id));
    });
  }
  showTab(tabId) {
    this.activeTab = tabId;
    this.tabsEl.querySelectorAll(".cs-tab").forEach((el) => {
      el.removeClass("active");
      if (el.dataset.tab === tabId) {
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
      cls: "cs-subtitle"
    });
    const inputRow = container.createDiv({ cls: "cs-input-row" });
    this.inputEl = new import_obsidian.TextComponent(inputRow);
    this.inputEl.setPlaceholder("e.g., 37622666, 10.1093/eurheartj/ehad195, or article title");
    this.inputEl.inputEl.addClass("cs-main-input");
    this.inputEl.inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter")
        this.doLookup();
    });
    const formatRow = container.createDiv({ cls: "cs-format-row" });
    formatRow.createSpan({ text: "Style: " });
    this.styleDropdown = new import_obsidian.DropdownComponent(formatRow);
    this.styleDropdown.addOption("vancouver", "Vancouver").addOption("apa", "APA").addOption("mla", "MLA").addOption("chicago", "Chicago").addOption("harvard", "Harvard").addOption("ieee", "IEEE").setValue(this.plugin.settings.citationStyle);
    formatRow.createSpan({ text: "  Format: " });
    this.formatDropdown = new import_obsidian.DropdownComponent(formatRow);
    this.formatDropdown.addOption("full", "Full (inline + endnote)").addOption("inline", "Inline only").addOption("endnote", "Endnote only").setValue(this.plugin.settings.defaultFormat);
    const buttonRow = container.createDiv({ cls: "cs-button-row" });
    new import_obsidian.ButtonComponent(buttonRow).setButtonText("Look Up").setCta().onClick(() => this.doLookup());
    new import_obsidian.ButtonComponent(buttonRow).setButtonText("Look Up + Insert").onClick(() => this.doLookupAndInsert());
    container.createDiv({ cls: "cs-results" });
    setTimeout(() => this.inputEl.inputEl.focus(), 50);
  }
  async doLookup() {
    const query = this.inputEl.getValue().trim();
    if (!query) {
      new import_obsidian.Notice("Please enter an identifier");
      return;
    }
    const selectedStyle = this.styleDropdown.getValue();
    if (selectedStyle !== this.plugin.settings.citationStyle) {
      this.plugin.settings.citationStyle = selectedStyle;
      await this.plugin.saveSettings();
    }
    const resultsEl = this.resultEl.querySelector(".cs-results");
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
    var _a;
    await this.doLookup();
    if ((_a = this.currentResult) == null ? void 0 : _a.success) {
      this.plugin.insertAtCursor(this.currentResult, this.formatDropdown.getValue());
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
      cls: "cs-subtitle"
    });
    const inputRow = container.createDiv({ cls: "cs-input-row" });
    const searchInput = new import_obsidian.TextComponent(inputRow);
    searchInput.setPlaceholder("e.g., ESC heart failure guidelines 2023");
    searchInput.inputEl.addClass("cs-main-input");
    searchInput.inputEl.addEventListener("keydown", (e) => {
      if (e.key === "Enter")
        doSearch();
    });
    const optionsRow = container.createDiv({ cls: "cs-options-row" });
    optionsRow.createSpan({ text: "Max results: " });
    const maxResultsDropdown = new import_obsidian.DropdownComponent(optionsRow);
    maxResultsDropdown.addOption("5", "5").addOption("10", "10").addOption("20", "20").setValue(String(this.plugin.settings.maxSearchResults));
    const buttonRow = container.createDiv({ cls: "cs-button-row" });
    new import_obsidian.ButtonComponent(buttonRow).setButtonText("Search PubMed").setCta().onClick(() => doSearch());
    const resultsEl = container.createDiv({ cls: "cs-results" });
    const doSearch = async () => {
      const query = searchInput.getValue().trim();
      if (!query) {
        new import_obsidian.Notice("Please enter a search query");
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
  displaySearchResults(container) {
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
      metaEl.setText(`${authors}${article.authors.length > 2 ? " et al." : ""} \u2022 ${article.journal} (${article.year})`);
      const idRow = item.createDiv({ cls: "cs-search-ids" });
      idRow.createEl("code", { text: `PMID: ${article.pmid}` });
      if (article.doi) {
        idRow.createEl("code", { text: `DOI: ${article.doi}` });
      }
      const actions = item.createDiv({ cls: "cs-search-actions" });
      new import_obsidian.ButtonComponent(actions).setButtonText("Get Citation").onClick(async () => {
        new import_obsidian.Notice("Looking up citation...");
        const result = await this.plugin.lookupCitation(article.pmid);
        if (result.success) {
          this.currentResult = result;
          this.showTab("lookup");
          const resultsEl = this.resultEl.querySelector(".cs-results");
          if (resultsEl) {
            this.displayCitationResult(resultsEl, result);
          }
        } else {
          new import_obsidian.Notice(`Error: ${result.error}`);
        }
      });
      new import_obsidian.ButtonComponent(actions).setButtonText("Insert").setCta().onClick(async () => {
        new import_obsidian.Notice("Looking up and inserting...");
        const result = await this.plugin.lookupCitation(article.pmid);
        if (result.success) {
          this.plugin.insertAtCursor(result, this.plugin.settings.defaultFormat);
          this.close();
        } else {
          new import_obsidian.Notice(`Error: ${result.error}`);
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
      cls: "cs-subtitle"
    });
    const textareaEl = container.createEl("textarea", { cls: "cs-batch-input" });
    textareaEl.placeholder = "37622666\n10.1093/eurheartj/ehad195\nPMC7039045\n...";
    textareaEl.rows = 8;
    const formatRow = container.createDiv({ cls: "cs-format-row" });
    formatRow.createSpan({ text: "Output format: " });
    const formatDropdown = new import_obsidian.DropdownComponent(formatRow);
    formatDropdown.addOption("full", "Full citations").addOption("inline", "Inline marks only").addOption("endnote", "Endnotes only").setValue(this.plugin.settings.defaultFormat);
    const buttonRow = container.createDiv({ cls: "cs-button-row" });
    new import_obsidian.ButtonComponent(buttonRow).setButtonText("Process Batch").setCta().onClick(() => processBatch());
    new import_obsidian.ButtonComponent(buttonRow).setButtonText("Process & Insert All").onClick(() => processBatchAndInsert());
    const resultsEl = container.createDiv({ cls: "cs-results" });
    const processBatch = async () => {
      const text = textareaEl.value.trim();
      if (!text) {
        new import_obsidian.Notice("Please enter some identifiers");
        return;
      }
      const identifiers = text.split("\n").map((s) => s.trim()).filter((s) => s && !s.startsWith("#"));
      resultsEl.empty();
      resultsEl.createEl("p", { text: `Processing ${identifiers.length} identifiers...`, cls: "cs-loading" });
      const results = [];
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
            error: String(error)
          });
        }
      }
      displayBatchResults(results);
    };
    const processBatchAndInsert = async () => {
      await processBatch();
      const view = this.app.workspace.getActiveViewOfType(import_obsidian.MarkdownView);
      if (!view) {
        new import_obsidian.Notice("No active editor");
        return;
      }
    };
    const displayBatchResults = (results) => {
      resultsEl.empty();
      const successCount = results.filter((r) => r.success).length;
      const failCount = results.length - successCount;
      resultsEl.createEl("h4", {
        text: `Results: ${successCount} successful, ${failCount} failed`
      });
      const format = formatDropdown.getValue();
      if (successCount > 0) {
        const successSection = resultsEl.createDiv({ cls: "cs-batch-section" });
        successSection.createEl("h5", { text: "\u2705 Successful" });
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
            output += `${r.inline_mark}
${r.full_citation}

`;
          }
        }
        outputArea.value = output;
        new import_obsidian.ButtonComponent(successSection).setButtonText("Copy All").onClick(() => {
          navigator.clipboard.writeText(output);
          new import_obsidian.Notice("Copied to clipboard!");
        });
      }
      if (failCount > 0) {
        const failSection = resultsEl.createDiv({ cls: "cs-batch-section cs-batch-failed" });
        failSection.createEl("h5", { text: "\u274C Failed" });
        const failList = failSection.createEl("ul");
        for (const r of results.filter((r2) => !r2.success)) {
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
    [...recent].reverse().forEach((item) => {
      const row = list.createDiv({ cls: "cs-recent-item" });
      const infoEl = row.createDiv({ cls: "cs-recent-info" });
      infoEl.createEl("code", { text: item.inline_mark });
      infoEl.createEl("span", {
        text: ` \u2022 ${new Date(item.timestamp).toLocaleDateString()}`,
        cls: "cs-recent-date"
      });
      const actions = row.createDiv({ cls: "cs-recent-actions" });
      new import_obsidian.ButtonComponent(actions).setButtonText("Copy").onClick(() => {
        navigator.clipboard.writeText(item.inline_mark);
        new import_obsidian.Notice("Copied!");
      });
      new import_obsidian.ButtonComponent(actions).setButtonText("Look Up Again").onClick(async () => {
        const result = await this.plugin.lookupCitation(item.identifier);
        if (result.success) {
          this.currentResult = result;
          this.showTab("lookup");
          const resultsEl = this.resultEl.querySelector(".cs-results");
          if (resultsEl) {
            this.displayCitationResult(resultsEl, result);
          }
        }
      });
      new import_obsidian.ButtonComponent(actions).setButtonText("Insert").setCta().onClick(async () => {
        const result = await this.plugin.lookupCitation(item.identifier);
        if (result.success) {
          this.plugin.insertAtCursor(result, this.plugin.settings.defaultFormat);
          this.close();
        }
      });
    });
    const clearRow = container.createDiv({ cls: "cs-clear-row" });
    new import_obsidian.ButtonComponent(clearRow).setButtonText("Clear History").onClick(async () => {
      this.plugin.settings.recentLookups = [];
      await this.plugin.saveSettings();
      this.renderRecentTab();
      new import_obsidian.Notice("History cleared");
    });
  }
  // =========================================================================
  // Display Citation Result
  // =========================================================================
  displayCitationResult(container, result) {
    var _a;
    container.empty();
    if (!result.success) {
      container.createEl("p", { text: `Error: ${result.error}`, cls: "cs-error" });
      return;
    }
    const inlineSection = container.createDiv({ cls: "cs-result-section" });
    inlineSection.createEl("h4", { text: "Inline Reference" });
    const inlineCode = inlineSection.createEl("code", { cls: "cs-inline-mark" });
    inlineCode.setText(result.inline_mark);
    new import_obsidian.ButtonComponent(inlineSection).setButtonText("Copy").onClick(() => {
      navigator.clipboard.writeText(result.inline_mark);
      new import_obsidian.Notice("Inline reference copied!");
    });
    const fullSection = container.createDiv({ cls: "cs-result-section" });
    fullSection.createEl("h4", { text: "Full Citation" });
    const fullText = fullSection.createDiv({ cls: "cs-full-citation" });
    fullText.setText(result.full_citation);
    new import_obsidian.ButtonComponent(fullSection).setButtonText("Copy").onClick(() => {
      navigator.clipboard.writeText(result.full_citation);
      new import_obsidian.Notice("Full citation copied!");
    });
    if (result.metadata) {
      const metaSection = container.createDiv({ cls: "cs-result-section cs-metadata-section" });
      const metaHeader = metaSection.createDiv({ cls: "cs-metadata-header" });
      metaHeader.createEl("h4", { text: "\u{1F4CA} Metadata" });
      const metaContent = metaSection.createDiv({ cls: "cs-metadata-content" });
      metaContent.style.display = "none";
      metaHeader.addEventListener("click", () => {
        metaContent.style.display = metaContent.style.display === "none" ? "block" : "none";
      });
      const meta = result.metadata;
      const table = metaContent.createEl("table", { cls: "cs-metadata-table" });
      const fields = [
        ["Title", meta.title],
        ["Authors", (_a = meta.authors) == null ? void 0 : _a.join(", ")],
        ["Journal", meta.journal_abbreviation || meta.journal],
        ["Year", meta.year],
        ["Volume/Issue", `${meta.volume || ""}${meta.issue ? `(${meta.issue})` : ""}`],
        ["Pages", meta.pages],
        ["PMID", meta.pmid],
        ["DOI", meta.doi]
      ];
      for (const [label, value] of fields) {
        if (value) {
          const row = table.createEl("tr");
          row.createEl("th", { text: label });
          row.createEl("td", { text: String(value) });
        }
      }
      if (meta.abstract) {
        metaContent.createEl("h5", { text: "Abstract" });
        metaContent.createEl("p", { text: meta.abstract, cls: "cs-abstract" });
      }
    }
    const actions = container.createDiv({ cls: "cs-actions" });
    new import_obsidian.ButtonComponent(actions).setButtonText("Insert Inline Only").onClick(() => {
      this.plugin.insertAtCursor(result, "inline");
      this.close();
    });
    new import_obsidian.ButtonComponent(actions).setButtonText("Insert Full Citation").onClick(() => {
      this.plugin.insertAtCursor(result, "endnote");
      this.close();
    });
    new import_obsidian.ButtonComponent(actions).setButtonText("Insert Both").setCta().onClick(() => {
      this.plugin.insertAtCursor(result, "full");
      this.close();
    });
  }
  onClose() {
    const { contentEl } = this;
    contentEl.empty();
  }
};
var QuickLookupModal = class extends import_obsidian.Modal {
  constructor(app, plugin, onSubmit) {
    super(app);
    this.plugin = plugin;
    this.onSubmit = onSubmit;
  }
  onOpen() {
    const { contentEl } = this;
    contentEl.createEl("h3", { text: "Quick Citation Lookup" });
    new import_obsidian.Setting(contentEl).setName("Identifier").setDesc("PMID, DOI, PMC ID, or title").addText((text) => {
      text.setPlaceholder("e.g., 37622666");
      text.inputEl.style.width = "300px";
      text.inputEl.addEventListener("keydown", async (e) => {
        if (e.key === "Enter") {
          const query = text.getValue().trim();
          if (query) {
            new import_obsidian.Notice("Looking up citation...");
            try {
              const result = await this.plugin.lookupCitation(query);
              this.onSubmit(result);
              this.close();
            } catch (error) {
              new import_obsidian.Notice(`Error: ${error}`);
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
};
var CitationSculptorSettingTab = class extends import_obsidian.PluginSettingTab {
  constructor(app, plugin) {
    super(app, plugin);
    this.plugin = plugin;
  }
  display() {
    const { containerEl } = this;
    containerEl.empty();
    containerEl.createEl("h2", { text: "CitationSculptor Settings" });
    containerEl.createEl("h3", { text: "MCP Server (Recommended)" });
    containerEl.createEl("p", {
      text: "Using the HTTP API is more efficient and avoids spawning new processes for each lookup.",
      cls: "setting-item-description"
    });
    new import_obsidian.Setting(containerEl).setName("Use HTTP API").setDesc("Connect to CitationSculptor MCP server via HTTP (recommended)").addToggle(
      (toggle) => toggle.setValue(this.plugin.settings.useHttpApi).onChange(async (value) => {
        this.plugin.settings.useHttpApi = value;
        await this.plugin.saveSettings();
        this.display();
      })
    );
    new import_obsidian.Setting(containerEl).setName("HTTP API URL").setDesc("URL of the CitationSculptor HTTP server").addText(
      (text) => text.setPlaceholder("http://127.0.0.1:3019").setValue(this.plugin.settings.httpApiUrl).onChange(async (value) => {
        this.plugin.settings.httpApiUrl = value;
        await this.plugin.saveSettings();
      })
    );
    new import_obsidian.Setting(containerEl).setName("Test HTTP Connection").setDesc("Check if the MCP server is running").addButton(
      (button) => button.setButtonText("Test").onClick(async () => {
        var _a;
        new import_obsidian.Notice("Testing HTTP connection...");
        try {
          const response = await (0, import_obsidian.requestUrl)({
            url: `${this.plugin.settings.httpApiUrl}/health`,
            method: "GET"
          });
          if (((_a = response.json) == null ? void 0 : _a.status) === "ok") {
            new import_obsidian.Notice(`\u2705 Connected! Server v${response.json.version}`);
          } else {
            new import_obsidian.Notice("\u274C Unexpected response from server");
          }
        } catch (error) {
          new import_obsidian.Notice(`\u274C Server not reachable: ${error.message}`);
        }
      })
    );
    containerEl.createEl("h3", { text: "CLI Fallback" });
    containerEl.createEl("p", {
      text: "Used when HTTP API is disabled or unavailable.",
      cls: "setting-item-description"
    });
    new import_obsidian.Setting(containerEl).setName("CitationSculptor Path").setDesc("Path to the CitationSculptor directory").addText(
      (text) => text.setPlaceholder("/path/to/CitationSculptor").setValue(this.plugin.settings.citationScriptPath).onChange(async (value) => {
        this.plugin.settings.citationScriptPath = value;
        await this.plugin.saveSettings();
      })
    );
    new import_obsidian.Setting(containerEl).setName("Python Path").setDesc("Path to the Python executable in the venv").addText(
      (text) => text.setPlaceholder("/path/to/.venv/bin/python").setValue(this.plugin.settings.pythonPath).onChange(async (value) => {
        this.plugin.settings.pythonPath = value;
        await this.plugin.saveSettings();
      })
    );
    containerEl.createEl("h3", { text: "Behavior" });
    new import_obsidian.Setting(containerEl).setName("Default Format").setDesc("Default citation format when inserting").addDropdown(
      (dropdown) => dropdown.addOption("full", "Full (inline + endnote)").addOption("inline", "Inline only").addOption("endnote", "Endnote only").setValue(this.plugin.settings.defaultFormat).onChange(async (value) => {
        this.plugin.settings.defaultFormat = value;
        await this.plugin.saveSettings();
      })
    );
    new import_obsidian.Setting(containerEl).setName("Citation Style").setDesc("Choose the citation style format (Vancouver, APA, MLA, etc.)").addDropdown(
      (dropdown) => dropdown.addOption("vancouver", "Vancouver (medical/scientific)").addOption("apa", "APA 7th (social sciences)").addOption("mla", "MLA 9th (humanities)").addOption("chicago", "Chicago/Turabian").addOption("harvard", "Harvard (author-date)").addOption("ieee", "IEEE (engineering)").setValue(this.plugin.settings.citationStyle).onChange(async (value) => {
        this.plugin.settings.citationStyle = value;
        await this.plugin.saveSettings();
      })
    );
    new import_obsidian.Setting(containerEl).setName("Auto Copy to Clipboard").setDesc("Automatically copy citations to clipboard when inserted").addToggle(
      (toggle) => toggle.setValue(this.plugin.settings.autoCopyToClipboard).onChange(async (value) => {
        this.plugin.settings.autoCopyToClipboard = value;
        await this.plugin.saveSettings();
      })
    );
    new import_obsidian.Setting(containerEl).setName("Insert at Cursor").setDesc("Automatically insert citation at cursor position").addToggle(
      (toggle) => toggle.setValue(this.plugin.settings.insertAtCursor).onChange(async (value) => {
        this.plugin.settings.insertAtCursor = value;
        await this.plugin.saveSettings();
      })
    );
    containerEl.createEl("h3", { text: "Search" });
    new import_obsidian.Setting(containerEl).setName("Max Search Results").setDesc("Maximum number of PubMed search results to show").addDropdown(
      (dropdown) => dropdown.addOption("5", "5").addOption("10", "10").addOption("20", "20").addOption("50", "50").setValue(String(this.plugin.settings.maxSearchResults)).onChange(async (value) => {
        this.plugin.settings.maxSearchResults = parseInt(value);
        await this.plugin.saveSettings();
      })
    );
    new import_obsidian.Setting(containerEl).setName("Show Abstracts in Search Results").setDesc("Display article abstracts in search results (slower)").addToggle(
      (toggle) => toggle.setValue(this.plugin.settings.showAbstractInResults).onChange(async (value) => {
        this.plugin.settings.showAbstractInResults = value;
        await this.plugin.saveSettings();
      })
    );
    containerEl.createEl("h3", { text: "\u{1F504} Bidirectional Settings Sync" });
    containerEl.createEl("p", {
      text: "Settings are automatically synchronized between Obsidian and the Web UI. Changes in either interface update the other within seconds.",
      cls: "setting-item-description"
    });
    new import_obsidian.Setting(containerEl).setName("Enable Sync").setDesc("Automatically sync settings with the CitationSculptor web server").addToggle(
      (toggle) => toggle.setValue(this.plugin.settings.syncWithServer).onChange(async (value) => {
        this.plugin.settings.syncWithServer = value;
        await this.plugin.saveSettings();
        if (value) {
          this.plugin.startPeriodicSync();
        } else {
          this.plugin.stopPeriodicSync();
        }
        this.display();
      })
    );
    if (this.plugin.settings.syncWithServer) {
      new import_obsidian.Setting(containerEl).setName("Sync Interval").setDesc("How often to check for changes from the web server (in seconds)").addDropdown(
        (dropdown) => dropdown.addOption("10", "10 seconds").addOption("30", "30 seconds").addOption("60", "1 minute").addOption("300", "5 minutes").setValue(String(this.plugin.settings.syncIntervalSeconds || 30)).onChange(async (value) => {
          this.plugin.settings.syncIntervalSeconds = parseInt(value);
          await this.plugin.saveSettings();
          this.plugin.restartPeriodicSync();
        })
      );
      const statusEl = containerEl.createDiv({ cls: "setting-item" });
      const statusInfo = statusEl.createDiv({ cls: "setting-item-info" });
      statusInfo.createDiv({ cls: "setting-item-name", text: "Sync Status" });
      const statusDesc = statusInfo.createDiv({ cls: "setting-item-description" });
      if (this.plugin.settings.lastServerSync) {
        const syncDate = new Date(this.plugin.settings.lastServerSync);
        statusDesc.setText(`Last synced: ${syncDate.toLocaleString()}`);
      } else {
        statusDesc.setText("Not yet synced");
      }
      new import_obsidian.Setting(containerEl).setName("Manual Sync").setDesc("Force sync now (settings are also synced automatically)").addButton(
        (button) => button.setButtonText("\u2193 Pull").onClick(async () => {
          new import_obsidian.Notice("Pulling settings from server...");
          const success = await this.plugin.manualSyncFromServer();
          if (success) {
            new import_obsidian.Notice("\u2705 Settings pulled from server");
            this.display();
          } else {
            new import_obsidian.Notice("\u274C Failed to pull. Is the server running?");
          }
        })
      ).addButton(
        (button) => button.setButtonText("\u2191 Push").onClick(async () => {
          new import_obsidian.Notice("Pushing settings to server...");
          const success = await this.plugin.manualSyncToServer();
          if (success) {
            new import_obsidian.Notice("\u2705 Settings pushed to server");
            this.display();
          } else {
            new import_obsidian.Notice("\u274C Failed to push. Is the server running?");
          }
        })
      );
      containerEl.createEl("p", {
        text: "Synced settings: Citation Style, Backup on Process, Max Search Results",
        cls: "setting-item-description"
      });
    }
    containerEl.createEl("h3", { text: "Safety" });
    new import_obsidian.Setting(containerEl).setName("Create Backup Before Processing").setDesc("Automatically create a timestamped backup of your note before processing citations (highly recommended)").addToggle(
      (toggle) => toggle.setValue(this.plugin.settings.createBackupBeforeProcessing).onChange(async (value) => {
        this.plugin.settings.createBackupBeforeProcessing = value;
        await this.plugin.saveSettings();
      })
    );
    if (this.plugin.settings.lastBackupPath) {
      new import_obsidian.Setting(containerEl).setName("Last Backup").setDesc(`Last backup: ${this.plugin.settings.lastBackupPath}`).addButton(
        (button) => button.setButtonText("Clear").onClick(async () => {
          this.plugin.settings.lastBackupPath = "";
          await this.plugin.saveSettings();
          this.display();
          new import_obsidian.Notice("Backup path cleared");
        })
      );
    }
    containerEl.createEl("h3", { text: "Cache & History" });
    new import_obsidian.Setting(containerEl).setName("Recent Lookups").setDesc(`${this.plugin.settings.recentLookups.length} items in history`).addButton(
      (button) => button.setButtonText("Clear History").onClick(async () => {
        this.plugin.settings.recentLookups = [];
        await this.plugin.saveSettings();
        this.display();
        new import_obsidian.Notice("History cleared");
      })
    );
    new import_obsidian.Setting(containerEl).setName("Test Connection").setDesc("Test connection to CitationSculptor").addButton(
      (button) => button.setButtonText("Test").onClick(async () => {
        new import_obsidian.Notice("Testing connection...");
        try {
          const result = await this.plugin.lookupCitation("32089132");
          if (result.success) {
            new import_obsidian.Notice("\u2705 Connection successful!");
          } else {
            new import_obsidian.Notice(`\u274C Error: ${result.error}`);
          }
        } catch (error) {
          new import_obsidian.Notice(`\u274C Error: ${error}`);
        }
      })
    );
  }
};
var CitationSculptorPlugin = class extends import_obsidian.Plugin {
  constructor() {
    super(...arguments);
    this.syncIntervalId = null;
  }
  async onload() {
    await this.loadSettings();
    this.startPeriodicSync();
    this.addRibbonIcon("quote-glyph", "CitationSculptor", () => {
      new CitationLookupModal(this.app, this).open();
    });
    this.addCommand({
      id: "open-citation-lookup",
      name: "Open Citation Lookup",
      callback: () => {
        new CitationLookupModal(this.app, this).open();
      }
    });
    this.addCommand({
      id: "quick-lookup",
      name: "Quick Lookup (PMID/DOI/Title)",
      editorCallback: (editor, view) => {
        new QuickLookupModal(this.app, this, (result) => {
          if (result.success) {
            this.insertCitationInEditor(editor, result, this.settings.defaultFormat);
          } else {
            new import_obsidian.Notice(`Error: ${result.error}`);
          }
        }).open();
      }
    });
    this.addCommand({
      id: "lookup-selection",
      name: "Look Up Selected Text",
      editorCallback: async (editor, view) => {
        const selection = editor.getSelection().trim();
        if (!selection) {
          new import_obsidian.Notice("Please select text to look up");
          return;
        }
        new import_obsidian.Notice("Looking up citation...");
        try {
          const result = await this.lookupCitation(selection);
          if (result.success) {
            this.insertCitationInEditor(editor, result, this.settings.defaultFormat);
          } else {
            new import_obsidian.Notice(`Error: ${result.error}`);
          }
        } catch (error) {
          new import_obsidian.Notice(`Error: ${error}`);
        }
      }
    });
    this.addCommand({
      id: "quick-lookup-inline",
      name: "Quick Lookup (Insert Inline Only)",
      editorCallback: (editor, view) => {
        new QuickLookupModal(this.app, this, (result) => {
          if (result.success) {
            editor.replaceSelection(result.inline_mark);
            if (this.settings.autoCopyToClipboard) {
              navigator.clipboard.writeText(result.inline_mark);
            }
            new import_obsidian.Notice("Inline reference inserted!");
          } else {
            new import_obsidian.Notice(`Error: ${result.error}`);
          }
        }).open();
      }
    });
    this.addCommand({
      id: "search-pubmed",
      name: "Search PubMed",
      callback: () => {
        const modal = new CitationLookupModal(this.app, this);
        modal.open();
        setTimeout(() => modal.showTab("search"), 100);
      }
    });
    this.addCommand({
      id: "batch-lookup",
      name: "Batch Citation Lookup",
      callback: () => {
        const modal = new CitationLookupModal(this.app, this);
        modal.open();
        setTimeout(() => modal.showTab("batch"), 100);
      }
    });
    this.addCommand({
      id: "recent-lookups",
      name: "Recent Citation Lookups",
      callback: () => {
        const modal = new CitationLookupModal(this.app, this);
        modal.open();
        setTimeout(() => modal.showTab("recent"), 100);
      }
    });
    this.addCommand({
      id: "process-current-note",
      name: "Process Current Note (Fix All Citations)",
      editorCallback: async (editor, view) => {
        const content = editor.getValue();
        if (!content) {
          new import_obsidian.Notice("Current note is empty");
          return;
        }
        const confirmed = await this.confirmProcessNote();
        if (!confirmed)
          return;
        let backupPath = null;
        if (this.settings.createBackupBeforeProcessing && view.file) {
          try {
            backupPath = await this.createBackup(view.file, content);
            new import_obsidian.Notice(`\u{1F4CB} Backup created: ${backupPath}`);
          } catch (backupError) {
            const proceed = await this.confirmProceedWithoutBackup(backupError.message);
            if (!proceed)
              return;
          }
        }
        new import_obsidian.Notice("Processing document... This may take a while for documents with many references.");
        try {
          const result = await this.processDocumentContent(content);
          if (result.success && result.processed_content) {
            editor.setValue(result.processed_content);
            const stats = result.statistics;
            if (stats) {
              new import_obsidian.Notice(`\u2713 Processed ${stats.processed}/${stats.total_references} citations (${stats.inline_replacements} inline replacements)`);
            } else {
              new import_obsidian.Notice("\u2713 Document processed successfully");
            }
            if (backupPath) {
              new import_obsidian.Notice(`\u{1F4BE} Backup saved at: ${backupPath}`);
            }
            if (result.failed_references && result.failed_references.length > 0) {
              new import_obsidian.Notice(`\u26A0\uFE0F ${result.failed_references.length} citations could not be resolved`);
            }
          } else {
            new import_obsidian.Notice(`Error: ${result.error || "Processing failed"}`);
            if (backupPath) {
              new import_obsidian.Notice(`Your backup is at: ${backupPath}`);
            }
          }
        } catch (e) {
          new import_obsidian.Notice(`Error: ${e.message}`);
          if (backupPath) {
            new import_obsidian.Notice(`Your backup is at: ${backupPath}`);
          }
        }
      }
    });
    this.addCommand({
      id: "restore-from-backup",
      name: "Restore from Last Backup",
      editorCallback: async (editor, view) => {
        if (!this.settings.lastBackupPath) {
          new import_obsidian.Notice("No backup available. Process a note first to create a backup.");
          return;
        }
        const confirmed = await this.confirmRestore();
        if (!confirmed)
          return;
        try {
          const backupFile = this.app.vault.getAbstractFileByPath(this.settings.lastBackupPath);
          if (!backupFile || !(backupFile instanceof this.app.vault.adapter.constructor)) {
            const backupContent = await this.app.vault.adapter.read(this.settings.lastBackupPath);
            if (backupContent) {
              editor.setValue(backupContent);
              new import_obsidian.Notice(`\u2713 Restored from backup: ${this.settings.lastBackupPath}`);
            } else {
              new import_obsidian.Notice(`Backup file not found: ${this.settings.lastBackupPath}`);
            }
          }
        } catch (e) {
          new import_obsidian.Notice(`Error restoring backup: ${e.message}`);
        }
      }
    });
    this.addSettingTab(new CitationSculptorSettingTab(this.app, this));
  }
  onunload() {
    this.stopPeriodicSync();
  }
  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
    if (this.settings.syncWithServer && this.settings.useHttpApi) {
      try {
        await this.syncSettingsFromServer();
      } catch (e) {
        console.warn("Failed to sync settings from server on load:", e);
      }
    }
  }
  async saveSettings() {
    await this.saveData(this.settings);
    if (this.settings.syncWithServer && this.settings.useHttpApi) {
      try {
        await this.syncSettingsToServer();
      } catch (e) {
        console.warn("Failed to sync settings to server:", e);
      }
    }
  }
  // =========================================================================
  // Server Settings Sync (Bidirectional)
  // =========================================================================
  /**
   * Start periodic sync to check for server-side changes.
   */
  startPeriodicSync() {
    if (!this.settings.syncWithServer || !this.settings.useHttpApi) {
      return;
    }
    this.stopPeriodicSync();
    const intervalMs = (this.settings.syncIntervalSeconds || 30) * 1e3;
    this.syncIntervalId = window.setInterval(async () => {
      if (this.settings.syncWithServer && this.settings.useHttpApi) {
        try {
          await this.checkAndSyncFromServer();
        } catch (e) {
          console.debug("Periodic sync check failed:", e);
        }
      }
    }, intervalMs);
    console.log(`CitationSculptor: Started periodic sync every ${this.settings.syncIntervalSeconds}s`);
  }
  /**
   * Stop periodic sync.
   */
  stopPeriodicSync() {
    if (this.syncIntervalId !== null) {
      window.clearInterval(this.syncIntervalId);
      this.syncIntervalId = null;
      console.log("CitationSculptor: Stopped periodic sync");
    }
  }
  /**
   * Restart periodic sync (e.g., when interval changes).
   */
  restartPeriodicSync() {
    this.stopPeriodicSync();
    this.startPeriodicSync();
  }
  /**
   * Check if server settings have changed and sync if needed.
   * Only pulls if the server's last_modified is newer than our last known.
   */
  async checkAndSyncFromServer() {
    var _a;
    try {
      const response = await (0, import_obsidian.requestUrl)({
        url: `${this.settings.httpApiUrl}/api/settings`,
        method: "GET"
      });
      const data = response.json;
      const serverModified = ((_a = data.settings) == null ? void 0 : _a.last_modified) || "";
      if (serverModified && serverModified !== this.settings.lastKnownServerModified) {
        console.log("CitationSculptor: Server settings changed, syncing...");
        await this.applyServerSettings(data.settings);
        return true;
      }
      return false;
    } catch (error) {
      console.debug("Check sync failed:", error.message);
      return false;
    }
  }
  /**
   * Apply settings from server response to local settings.
   */
  async applyServerSettings(serverSettings) {
    let changed = false;
    if (serverSettings.default_citation_style && serverSettings.default_citation_style !== this.settings.citationStyle) {
      this.settings.citationStyle = serverSettings.default_citation_style;
      changed = true;
    }
    if (serverSettings.create_backup_on_process !== void 0 && serverSettings.create_backup_on_process !== this.settings.createBackupBeforeProcessing) {
      this.settings.createBackupBeforeProcessing = serverSettings.create_backup_on_process;
      changed = true;
    }
    if (serverSettings.max_search_results !== void 0 && serverSettings.max_search_results !== this.settings.maxSearchResults) {
      this.settings.maxSearchResults = serverSettings.max_search_results;
      changed = true;
    }
    this.settings.lastServerSync = (/* @__PURE__ */ new Date()).toISOString();
    this.settings.lastKnownServerModified = serverSettings.last_modified || "";
    await this.saveData(this.settings);
    if (changed) {
      console.log("CitationSculptor: Settings updated from server");
    }
  }
  /**
   * Fetch settings from the server and merge with local settings.
   * Server settings take precedence for shared settings.
   */
  async syncSettingsFromServer() {
    try {
      const response = await (0, import_obsidian.requestUrl)({
        url: `${this.settings.httpApiUrl}/api/settings`,
        method: "GET"
      });
      const data = response.json;
      await this.applyServerSettings(data.settings);
    } catch (error) {
      throw new Error(`Failed to fetch settings from server: ${error.message}`);
    }
  }
  /**
   * Push local settings to the server.
   * Only pushes settings that the server understands.
   */
  async syncSettingsToServer() {
    var _a;
    try {
      const settingsToSync = {
        default_citation_style: this.settings.citationStyle,
        create_backup_on_process: this.settings.createBackupBeforeProcessing,
        max_search_results: this.settings.maxSearchResults
      };
      const response = await (0, import_obsidian.requestUrl)({
        url: `${this.settings.httpApiUrl}/api/settings`,
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(settingsToSync)
      });
      const data = response.json;
      if ((_a = data.settings) == null ? void 0 : _a.last_modified) {
        this.settings.lastKnownServerModified = data.settings.last_modified;
      }
      this.settings.lastServerSync = (/* @__PURE__ */ new Date()).toISOString();
      await this.saveData(this.settings);
    } catch (error) {
      throw new Error(`Failed to push settings to server: ${error.message}`);
    }
  }
  /**
   * Manually trigger a settings sync from the server.
   * Returns true if successful, false otherwise.
   */
  async manualSyncFromServer() {
    try {
      await this.syncSettingsFromServer();
      return true;
    } catch (error) {
      console.error("Manual sync failed:", error);
      return false;
    }
  }
  /**
   * Manually trigger a settings push to the server.
   * Returns true if successful, false otherwise.
   */
  async manualSyncToServer() {
    try {
      await this.syncSettingsToServer();
      return true;
    } catch (error) {
      console.error("Manual push failed:", error);
      return false;
    }
  }
  addRecentLookup(identifier, inline_mark) {
    this.settings.recentLookups = this.settings.recentLookups.filter(
      (r) => r.identifier !== identifier
    );
    this.settings.recentLookups.push({
      identifier,
      inline_mark,
      timestamp: Date.now()
    });
    if (this.settings.recentLookups.length > 50) {
      this.settings.recentLookups = this.settings.recentLookups.slice(-50);
    }
    this.saveSettings();
  }
  // =========================================================================
  // Citation Lookup via MCP Server HTTP API (preferred) or CLI fallback
  // =========================================================================
  async lookupCitation(identifier) {
    if (this.settings.useHttpApi) {
      try {
        const style = this.settings.citationStyle || "vancouver";
        const response = await (0, import_obsidian.requestUrl)({
          url: `${this.settings.httpApiUrl}/api/lookup?id=${encodeURIComponent(identifier)}&style=${style}`,
          method: "GET"
        });
        const result = response.json;
        return {
          success: result.success,
          identifier: result.identifier || identifier,
          identifier_type: result.identifier_type || "unknown",
          inline_mark: result.inline_mark || "",
          endnote_citation: result.endnote_citation || result.full_citation || "",
          full_citation: result.full_citation || "",
          metadata: result.metadata,
          error: result.error
        };
      } catch (httpError) {
        console.warn("HTTP API unavailable, falling back to CLI:", httpError.message);
      }
    }
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
        error: result.error
      };
    } catch (error) {
      return {
        success: false,
        identifier,
        identifier_type: "unknown",
        inline_mark: "",
        endnote_citation: "",
        full_citation: "",
        error: error.message || "Unknown error"
      };
    }
  }
  async searchPubMed(query, maxResults = 10) {
    var _a, _b, _c, _d;
    if (this.settings.useHttpApi) {
      try {
        const response = await (0, import_obsidian.requestUrl)({
          url: `${this.settings.httpApiUrl}/api/search?q=${encodeURIComponent(query)}&max=${maxResults}`,
          method: "GET"
        });
        const data = response.json;
        return data.results || [];
      } catch (httpError) {
        console.warn("HTTP API unavailable, falling back to direct PubMed:", httpError.message);
      }
    }
    const baseUrl = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils";
    const searchUrl = `${baseUrl}/esearch.fcgi?db=pubmed&term=${encodeURIComponent(query)}&retmax=${maxResults}&retmode=json`;
    try {
      const searchResponse = await (0, import_obsidian.requestUrl)({ url: searchUrl });
      const searchData = searchResponse.json;
      const pmids = ((_a = searchData.esearchresult) == null ? void 0 : _a.idlist) || [];
      if (pmids.length === 0)
        return [];
      const summaryUrl = `${baseUrl}/esummary.fcgi?db=pubmed&id=${pmids.join(",")}&retmode=json`;
      const summaryResponse = await (0, import_obsidian.requestUrl)({ url: summaryUrl });
      const summaryData = summaryResponse.json;
      const articles = [];
      for (const pmid of pmids) {
        const doc = (_b = summaryData.result) == null ? void 0 : _b[pmid];
        if (doc) {
          articles.push({
            pmid,
            title: doc.title || "Unknown",
            authors: (doc.authors || []).map((a) => a.name),
            journal: doc.source || "Unknown",
            year: ((_c = doc.pubdate) == null ? void 0 : _c.split(" ")[0]) || "",
            doi: ((_d = doc.elocationid) == null ? void 0 : _d.replace("doi: ", "")) || ""
          });
        }
      }
      return articles;
    } catch (error) {
      console.error("PubMed search error:", error);
      return [];
    }
  }
  // =========================================================================
  // Document Processing
  // =========================================================================
  async confirmProcessNote() {
    return new Promise((resolve) => {
      const modal = new import_obsidian.Modal(this.app);
      modal.titleEl.setText("Process Current Note?");
      modal.contentEl.createEl("p", {
        text: "This will process all citations in the current document, looking them up via PubMed/CrossRef and replacing inline references with proper formatted citations."
      });
      if (this.settings.createBackupBeforeProcessing) {
        modal.contentEl.createEl("p", {
          text: "\u2705 A backup will be created automatically before processing.",
          cls: "mod-success"
        });
      } else {
        modal.contentEl.createEl("p", {
          text: "\u26A0\uFE0F Backups are disabled. Enable them in settings for safety.",
          cls: "mod-warning"
        });
      }
      const buttonContainer = modal.contentEl.createDiv({ cls: "modal-button-container" });
      const cancelButton = buttonContainer.createEl("button", { text: "Cancel" });
      cancelButton.addEventListener("click", () => {
        modal.close();
        resolve(false);
      });
      const confirmButton = buttonContainer.createEl("button", {
        text: "Process Document",
        cls: "mod-cta"
      });
      confirmButton.addEventListener("click", () => {
        modal.close();
        resolve(true);
      });
      modal.open();
    });
  }
  async confirmProceedWithoutBackup(errorMsg) {
    return new Promise((resolve) => {
      const modal = new import_obsidian.Modal(this.app);
      modal.titleEl.setText("\u26A0\uFE0F Backup Failed");
      modal.contentEl.createEl("p", {
        text: `Could not create backup: ${errorMsg}`
      });
      modal.contentEl.createEl("p", {
        text: "Do you want to proceed without a backup? This is not recommended.",
        cls: "mod-warning"
      });
      const buttonContainer = modal.contentEl.createDiv({ cls: "modal-button-container" });
      const cancelButton = buttonContainer.createEl("button", { text: "Cancel" });
      cancelButton.addEventListener("click", () => {
        modal.close();
        resolve(false);
      });
      const confirmButton = buttonContainer.createEl("button", {
        text: "Proceed Without Backup",
        cls: "mod-warning"
      });
      confirmButton.addEventListener("click", () => {
        modal.close();
        resolve(true);
      });
      modal.open();
    });
  }
  async confirmRestore() {
    return new Promise((resolve) => {
      const modal = new import_obsidian.Modal(this.app);
      modal.titleEl.setText("Restore from Backup?");
      modal.contentEl.createEl("p", {
        text: `This will replace the current note content with the backup from: ${this.settings.lastBackupPath}`
      });
      modal.contentEl.createEl("p", {
        text: "Current changes will be lost.",
        cls: "mod-warning"
      });
      const buttonContainer = modal.contentEl.createDiv({ cls: "modal-button-container" });
      const cancelButton = buttonContainer.createEl("button", { text: "Cancel" });
      cancelButton.addEventListener("click", () => {
        modal.close();
        resolve(false);
      });
      const confirmButton = buttonContainer.createEl("button", {
        text: "Restore",
        cls: "mod-cta"
      });
      confirmButton.addEventListener("click", () => {
        modal.close();
        resolve(true);
      });
      modal.open();
    });
  }
  async createBackup(file, content) {
    var _a;
    const timestamp = (/* @__PURE__ */ new Date()).toISOString().replace(/[:.]/g, "-").slice(0, 19);
    const baseName = file.basename;
    const backupName = `${baseName}_backup_${timestamp}.md`;
    const parentPath = ((_a = file.parent) == null ? void 0 : _a.path) || "";
    const backupPath = parentPath ? `${parentPath}/${backupName}` : backupName;
    await this.app.vault.create(backupPath, content);
    this.settings.lastBackupPath = backupPath;
    await this.saveSettings();
    return backupPath;
  }
  async processDocumentContent(content) {
    if (!this.settings.useHttpApi) {
      return {
        success: false,
        error: "Document processing requires the HTTP API to be enabled. Please enable it in settings."
      };
    }
    try {
      const style = this.settings.citationStyle || "vancouver";
      const response = await (0, import_obsidian.requestUrl)({
        url: `${this.settings.httpApiUrl}/api/process-document`,
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          content,
          style
        })
      });
      return response.json;
    } catch (error) {
      return {
        success: false,
        error: error.message || "Failed to process document"
      };
    }
  }
  insertAtCursor(result, format = "full") {
    const view = this.app.workspace.getActiveViewOfType(import_obsidian.MarkdownView);
    if (view) {
      this.insertCitationInEditor(view.editor, result, format);
    }
  }
  insertCitationInEditor(editor, result, format) {
    const cursor = editor.getCursor();
    if (format === "inline") {
      editor.replaceSelection(result.inline_mark);
      if (this.settings.autoCopyToClipboard) {
        navigator.clipboard.writeText(result.inline_mark);
      }
      new import_obsidian.Notice("Inline reference inserted!");
      return;
    }
    if (format === "endnote") {
      editor.replaceSelection(result.full_citation);
      if (this.settings.autoCopyToClipboard) {
        navigator.clipboard.writeText(result.full_citation);
      }
      new import_obsidian.Notice("Citation inserted!");
      return;
    }
    editor.replaceSelection(result.inline_mark);
    const doc = editor.getValue();
    if (!doc.includes(result.full_citation)) {
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
    new import_obsidian.Notice("Citation inserted!");
  }
};
