/**
 * LedgerLens Web Application Logic
 * Interactive state management, document uploads, live audit inspection, and exports.
 */

let invoicesState = [];
let summaryState = null;
let currentTaxRate = 30.0;
let currentEditingId = null;

// DOM Elements
const invoicesTableBody = document.getElementById('invoicesTableBody');
const searchInput = document.getElementById('searchInput');
const fileInput = document.getElementById('fileInput');
const dropzone = document.getElementById('dropzone');
const taxSlider = document.getElementById('taxSlider');
const taxRateDisplay = document.getElementById('taxRateDisplay');

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    refreshAllData();
});

function setupEventListeners() {
    // Dropzone Drag & Drop
    ['dragenter', 'dragover'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.add('dragover');
        });
    });

    ['dragleave', 'drop'].forEach(eventName => {
        dropzone.addEventListener(eventName, (e) => {
            e.preventDefault();
            e.stopPropagation();
            dropzone.classList.remove('dragover');
        });
    });

    dropzone.addEventListener('drop', (e) => {
        const dt = e.dataTransfer;
        const files = dt.files;
        if (files.length > 0) {
            handleFileUpload(files[0]);
        }
    });

    dropzone.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files.length > 0) {
            handleFileUpload(e.target.files[0]);
        }
    });

    // Search filter
    searchInput.addEventListener('input', (e) => {
        renderTable(e.target.value.toLowerCase());
    });

    // Tax slider
    taxSlider.addEventListener('input', (e) => {
        currentTaxRate = parseFloat(e.target.value);
        taxRateDisplay.textContent = `${currentTaxRate}%`;
        const exportBtn = document.getElementById('btnExportReport');
        if (exportBtn) {
            exportBtn.href = `/api/export/report?tax_rate=${currentTaxRate}`;
        }
        fetchSummary();
    });
}

// Fetch all data
async function refreshAllData() {
    try {
        await Promise.all([fetchInvoices(), fetchSummary()]);
    } catch (err) {
        showToast('Error connecting to backend API', 'error');
    }
}

async function fetchInvoices() {
    const res = await fetch('/api/invoices');
    if (res.ok) {
        invoicesState = await res.json();
        renderTable(searchInput.value.toLowerCase());
    }
}

async function fetchSummary() {
    const res = await fetch(`/api/summary?tax_rate=${currentTaxRate}`);
    if (res.ok) {
        summaryState = await res.json();
        renderKPIs();
        renderCategoryBreakdown();
    }
}

// Render KPI Cards
function renderKPIs() {
    if (!summaryState) return;

    document.getElementById('kpiTotalSpend').textContent = `$${summaryState.total_spend.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    document.getElementById('kpiDeductible').textContent = `$${summaryState.total_deductible.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    document.getElementById('kpiTaxSavings').textContent = `$${summaryState.estimated_tax_savings.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
    
    const riskElem = document.getElementById('kpiAuditRisk');
    riskElem.textContent = summaryState.audit_risk_score;
    riskElem.className = `kpi-value ${summaryState.audit_risk_score.toLowerCase()}-risk`;

    document.getElementById('kpiDocsCount').textContent = `${summaryState.total_documents} Verified Invoices`;
    document.getElementById('kpiFlagsCount').textContent = `${summaryState.flagged_issues_count} Potential Audit Flags`;
}

// Render Categories
function renderCategoryBreakdown() {
    const container = document.getElementById('categoryProgressContainer');
    if (!container || !summaryState) return;

    const categories = summaryState.categories_breakdown;
    const total = summaryState.total_spend || 1;

    container.innerHTML = Object.entries(categories)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5)
        .map(([cat, amt]) => {
            const pct = Math.round((amt / total) * 100);
            return `
                <div class="cat-item">
                    <div class="cat-labels">
                        <span class="cat-name">${escapeHtml(cat)}</span>
                        <span class="cat-amount">$${amt.toLocaleString('en-US', { minimumFractionDigits: 2 })} (${pct}%)</span>
                    </div>
                    <div class="cat-bar-bg">
                        <div class="cat-bar-fill" style="width: ${pct}%"></div>
                    </div>
                </div>
            `;
        }).join('');
}

// Render Invoices Table
function renderTable(filterQuery = '') {
    const filtered = invoicesState.filter(inv => {
        if (!filterQuery) return true;
        const target = `${inv.vendor} ${inv.category} ${inv.invoice_number} ${inv.filename}`.toLowerCase();
        return target.includes(filterQuery);
    });

    if (filtered.length === 0) {
        invoicesTableBody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; padding: 3rem; color: var(--text-muted);">
                    No invoices match your search. Upload an invoice or click one of the quick test presets.
                </td>
            </tr>
        `;
        return;
    }

    invoicesTableBody.innerHTML = filtered.map(inv => {
        // Category badge style
        let badgeClass = 'badge-other';
        const catLower = inv.category.toLowerCase();
        if (catLower.includes('software') || catLower.includes('cloud')) badgeClass = 'badge-saas';
        else if (catLower.includes('contract') || catLower.includes('labor')) badgeClass = 'badge-labor';
        else if (catLower.includes('meal')) badgeClass = 'badge-meals';
        else if (catLower.includes('travel')) badgeClass = 'badge-travel';
        else if (catLower.includes('office') || catLower.includes('supplies')) badgeClass = 'badge-office';

        // Audit flags representation
        let flagHtml = `<span class="flag-pill flag-clean">✓ Verified</span>`;
        if (inv.audit_flags && inv.audit_flags.length > 0) {
            const hasCrit = inv.audit_flags.some(f => f.severity === 'critical');
            const hasWarn = inv.audit_flags.some(f => f.severity === 'warning');
            const flagCount = inv.audit_flags.length;
            
            if (hasCrit) {
                flagHtml = `<span class="flag-pill flag-critical">⚠ ${flagCount} Critical</span>`;
            } else if (hasWarn) {
                flagHtml = `<span class="flag-pill flag-warn">⚡ ${flagCount} Flags</span>`;
            } else {
                flagHtml = `<span class="flag-pill flag-clean">ℹ ${flagCount} Notes</span>`;
            }
        }

        return `
            <tr>
                <td>
                    <div class="vendor-col">
                        <span class="vendor-name">${escapeHtml(inv.vendor)}</span>
                        <span class="invoice-subtext">${escapeHtml(inv.filename)}</span>
                    </div>
                </td>
                <td style="white-space: nowrap; color: var(--text-muted);">${escapeHtml(inv.date || 'N/A')}</td>
                <td>
                    <span class="badge ${badgeClass}">${escapeHtml(inv.category)}</span>
                </td>
                <td>
                    <div style="display: flex; flex-direction: column;">
                        <span class="amount-total">$${inv.total.toFixed(2)}</span>
                        <span class="invoice-subtext">${inv.currency}</span>
                    </div>
                </td>
                <td>
                    <div style="display: flex; flex-direction: column;">
                        <span class="amount-deductible">$${inv.deductible_amount.toFixed(2)}</span>
                        <span class="invoice-subtext">${inv.deductible_percentage}% deductible</span>
                    </div>
                </td>
                <td>${flagHtml}</td>
                <td>
                    <div class="action-btns">
                        <button class="btn-icon" title="View Audit Details" onclick="openInvoiceModal('${inv.id}')">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
                        </button>
                        <button class="btn-icon delete" title="Delete Record" onclick="deleteInvoice('${inv.id}')">
                            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/></svg>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join('');
}

// Upload Handler
async function handleFileUpload(file) {
    showToast(`Parsing ${file.name} with open-source AI engine...`, 'info');
    
    const formData = new FormData();
    formData.append('file', file);

    try {
        const res = await fetch('/api/invoices/upload', {
            method: 'POST',
            body: formData
        });

        if (res.ok) {
            const data = await res.json();
            showToast(`Extracted ${data.vendor} ($${data.total.toFixed(2)}) successfully!`, 'success');
            await refreshAllData();
            openInvoiceModal(data.id);
        } else {
            const err = await res.json();
            showToast(`Upload failed: ${err.detail || 'Could not parse document'}`, 'error');
        }
    } catch (e) {
        showToast('Network error during upload', 'error');
    }
}

// Modal Inspector & Editor
function openInvoiceModal(invoiceId) {
    const inv = invoicesState.find(item => item.id === invoiceId);
    if (!inv) return;

    currentEditingId = invoiceId;

    document.getElementById('modalVendor').value = inv.vendor;
    document.getElementById('modalInvNumber').value = inv.invoice_number || '';
    document.getElementById('modalDate').value = inv.date || '';
    document.getElementById('modalCategory').value = inv.category;
    document.getElementById('modalSubtotal').value = inv.subtotal.toFixed(2);
    document.getElementById('modalTax').value = inv.tax.toFixed(2);
    document.getElementById('modalTotal').value = inv.total.toFixed(2);
    document.getElementById('modalDeductiblePct').value = inv.deductible_percentage;
    document.getElementById('modalPurpose').value = inv.business_purpose || '';
    document.getElementById('modalScheduleC').textContent = inv.schedule_c_line;
    document.getElementById('modalConfidence').textContent = `${Math.round(inv.confidence_score * 100)}% (${inv.extraction_method})`;

    // Render Audit Flags List
    const flagsContainer = document.getElementById('modalFlagsList');
    if (inv.audit_flags && inv.audit_flags.length > 0) {
        flagsContainer.innerHTML = inv.audit_flags.map(f => `
            <div style="background: rgba(255,255,255,0.03); border-left: 3px solid ${f.severity === 'critical' ? 'var(--rose)' : (f.severity === 'warning' ? 'var(--amber)' : 'var(--indigo)')}; padding: 0.75rem 1rem; border-radius: 4px; margin-bottom: 0.5rem;">
                <div style="font-weight: 700; font-size: 0.85rem; color: var(--text-main); margin-bottom: 0.2rem;">${escapeHtml(f.title)}</div>
                <div style="font-size: 0.8rem; color: var(--text-muted); margin-bottom: 0.3rem;">${escapeHtml(f.message)}</div>
                ${f.recommendation ? `<div style="font-size: 0.75rem; color: #a5b4fc;">💡 Recommendation: ${escapeHtml(f.recommendation)}</div>` : ''}
            </div>
        `).join('');
    } else {
        flagsContainer.innerHTML = `<div style="color: var(--emerald); font-size: 0.85rem;">✓ No audit flags detected. Full compliance verification passed.</div>`;
    }

    // Render Line items
    const itemsContainer = document.getElementById('modalLineItems');
    if (inv.line_items && inv.line_items.length > 0) {
        itemsContainer.innerHTML = inv.line_items.map(it => `
            <div style="display: flex; justify-content: space-between; padding: 0.5rem 0; border-bottom: 1px solid rgba(255,255,255,0.04); font-size: 0.825rem;">
                <span>${it.quantity}x ${escapeHtml(it.description)}</span>
                <span style="font-weight: 600;">$${it.amount.toFixed(2)}</span>
            </div>
        `).join('');
    } else {
        itemsContainer.innerHTML = `<div style="color: var(--text-sub); font-size: 0.8rem;">No itemized line details available.</div>`;
    }

    document.getElementById('invoiceModal').classList.add('active');
}

function closeInvoiceModal() {
    document.getElementById('invoiceModal').classList.remove('active');
    currentEditingId = null;
}

// Save Modal Changes
async function saveInvoiceChanges() {
    if (!currentEditingId) return;

    const original = invoicesState.find(item => item.id === currentEditingId);
    if (!original) return;

    const updated = {
        ...original,
        vendor: document.getElementById('modalVendor').value,
        invoice_number: document.getElementById('modalInvNumber').value,
        date: document.getElementById('modalDate').value,
        category: document.getElementById('modalCategory').value,
        subtotal: parseFloat(document.getElementById('modalSubtotal').value) || 0.0,
        tax: parseFloat(document.getElementById('modalTax').value) || 0.0,
        total: parseFloat(document.getElementById('modalTotal').value) || 0.0,
        deductible_percentage: parseFloat(document.getElementById('modalDeductiblePct').value) || 100.0,
        business_purpose: document.getElementById('modalPurpose').value
    };

    try {
        const res = await fetch(`/api/invoices/${currentEditingId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updated)
        });

        if (res.ok) {
            showToast('Invoice updated successfully', 'success');
            closeInvoiceModal();
            await refreshAllData();
        } else {
            showToast('Failed to update invoice', 'error');
        }
    } catch (e) {
        showToast('Error saving changes', 'error');
    }
}

// Delete Invoice
async function deleteInvoice(invoiceId) {
    if (!confirm('Are you sure you want to remove this invoice?')) return;

    try {
        const res = await fetch(`/api/invoices/${invoiceId}`, { method: 'DELETE' });
        if (res.ok) {
            showToast('Invoice removed', 'info');
            await refreshAllData();
        }
    } catch (e) {
        showToast('Error deleting invoice', 'error');
    }
}

// 1-Click Sample Inserter for quick testing
async function loadSamplePreset(vendorName, totalAmount, categoryName, desc) {
    const fakeText = `${vendorName}\nInvoice #: INV-DEMO-${Math.floor(Math.random() * 89999 + 10000)}\nDate: 2026-10-15\nCategory: ${categoryName}\nDescription: ${desc}\nSubtotal: $${(totalAmount * 0.9).toFixed(2)}\nTax: $${(totalAmount * 0.1).toFixed(2)}\nTotal Amount: $${totalAmount.toFixed(2)}`;
    
    const blob = new Blob([fakeText], { type: 'text/plain' });
    const file = new File([blob], `${vendorName.toLowerCase().replace(/[^a-z0-9]/g, '_')}_receipt.txt`, { type: 'text/plain' });
    
    await handleFileUpload(file);
}

// Reset sample data
async function resetToDefaults() {
    if (!confirm('Reset all invoices back to default freelance demo set?')) return;
    try {
        const res = await fetch('/api/invoices/reset-samples', { method: 'POST' });
        if (res.ok) {
            showToast('Sample dataset restored', 'success');
            await refreshAllData();
        }
    } catch (e) {
        showToast('Failed to reset samples', 'error');
    }
}

// Open AI Settings Modal
async function openSettingsModal() {
    try {
        const res = await fetch('/api/settings');
        if (res.ok) {
            const data = await res.json();
            if (data.provider) document.getElementById('aiProviderSelect').value = data.provider;
            if (data.model_name) document.getElementById('aiModelInput').value = data.model_name;
            if (data.ollama_url) document.getElementById('aiOllamaUrl').value = data.ollama_url;
        }
    } catch (e) {
        console.warn('Could not load current settings:', e);
    }
    document.getElementById('settingsModal').classList.add('active');
}

function closeSettingsModal() {
    document.getElementById('settingsModal').classList.remove('active');
}

async function saveAISettings() {
    const provider = document.getElementById('aiProviderSelect').value;
    const model = document.getElementById('aiModelInput').value;
    const ollamaUrl = document.getElementById('aiOllamaUrl').value;

    const payload = {
        provider: provider,
        model_name: model,
        ollama_url: ollamaUrl
    };

    try {
        const res = await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        if (res.ok) {
            showToast('AI engine configuration saved', 'success');
            closeSettingsModal();
        }
    } catch (e) {
        showToast('Failed to update AI settings', 'error');
    }
}

// Toast helper
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = 'toast';
    
    let icon = 'ℹ️';
    if (type === 'success') icon = '✅';
    else if (type === 'error') icon = '❌';

    toast.innerHTML = `<span>${icon}</span> <span>${escapeHtml(message)}</span>`;
    container.appendChild(toast);

    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
