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
  autoCopyToClipboard: true,
  insertAtCursor: true,
  showAbstractInResults: false,
  maxSearchResults: 10,
  recentLookups: [],
  // HTTP API settings (preferred for efficiency)
  useHttpApi: true,
  httpApiUrl: "http://127.0.0.1:3018"
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
    formatRow.createSpan({ text: "Format: " });
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
      (text) => text.setPlaceholder("http://127.0.0.1:3018").setValue(this.plugin.settings.httpApiUrl).onChange(async (value) => {
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
  async onload() {
    await this.loadSettings();
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
    this.addSettingTab(new CitationSculptorSettingTab(this.app, this));
  }
  onunload() {
  }
  async loadSettings() {
    this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
  }
  async saveSettings() {
    await this.saveData(this.settings);
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
        const response = await (0, import_obsidian.requestUrl)({
          url: `${this.settings.httpApiUrl}/api/lookup?id=${encodeURIComponent(identifier)}`,
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
