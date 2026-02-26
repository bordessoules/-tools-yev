/**
 * Timeline JS — Geekadomicile Client Timeline
 *
 * Filtres multi-sélection (type + équipement), recherche plein texte,
 * overlay pièces jointes (image/PDF + OCR), regroupement inventaire.
 */
'use strict';

(function() {

// -- Constantes CSS --
var HIDDEN_CLS    = 'hidden-ex';
var ACTIVE_CLS    = 'active';
var GROUPED_CLS   = 'eq-grouped';
var EQ_ACTIVE_CLS = 'eq-active';
var LINKED_CLS    = 'eq-inv-linked';

// -- Helpers --

/** Échappe une chaîne pour injection sûre dans innerHTML. */
function escHtml(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
}

function qsa(sel) { return document.querySelectorAll(sel); }

// ========================================================
//  Panneau équipements (toggle)
// ========================================================

window.toggleEqPanel = function(hdr) {
    var body = hdr.nextElementSibling;
    var open = body.style.display !== 'none';
    body.style.display = open ? 'none' : 'block';
    hdr.classList.toggle('open', !open);
};

// ========================================================
//  Filtre par type (multi-sélection)
// ========================================================

var _activeTypeFilters = [];

window.filterType = function(typeKey) {
    clearEqFilter();
    var idx = _activeTypeFilters.indexOf(typeKey);
    if (idx !== -1) _activeTypeFilters.splice(idx, 1);
    else _activeTypeFilters.push(typeKey);

    qsa('.ex-row').forEach(function(el) {
        if (_activeTypeFilters.length === 0) el.classList.remove(HIDDEN_CLS);
        else el.classList.toggle(HIDDEN_CLS, _activeTypeFilters.indexOf(el.dataset.type) === -1);
    });
    qsa('.type-pill').forEach(function(p) {
        p.classList.toggle(ACTIVE_CLS, _activeTypeFilters.indexOf(p.dataset.type) !== -1);
    });
};

function clearTypeFilter() {
    _activeTypeFilters = [];
    qsa('.type-pill').forEach(function(p) { p.classList.remove(ACTIVE_CLS); });
}

// ========================================================
//  Recherche plein texte
// ========================================================

window.doSearch = function(q) {
    clearEqFilter();
    clearTypeFilter();
    q = q.toLowerCase().trim();
    qsa('.ex-row').forEach(function(r) {
        if (!q) { r.classList.remove(HIDDEN_CLS); return; }
        var text = (r.dataset.text || '') + ' ' + r.querySelector('.ex-subj').textContent.toLowerCase();
        r.classList.toggle(HIDDEN_CLS, text.indexOf(q) === -1);
    });
};

// ========================================================
//  Toggle contenu OCR
// ========================================================

window.toggleOcr = function(ocrId) {
    var el = document.getElementById(ocrId);
    if (el) el.classList.toggle('open');
};

// ========================================================
//  Overlay pièces jointes (split-view)
// ========================================================

window.openAttOverlay = function(el) {
    var href  = el.dataset.href;
    var title = el.dataset.title || '';
    var type  = el.dataset.type || 'other';
    var ocrId = el.dataset.ocr || '';

    var overlay = document.getElementById('att-overlay');
    var left    = document.getElementById('att-overlay-left');
    var right   = document.getElementById('att-overlay-right');

    document.getElementById('att-overlay-newtab').href = href;
    document.getElementById('att-overlay-title').textContent = title;

    // Gauche : aperçu du fichier (sanitized)
    if (type === 'image') {
        var img = document.createElement('img');
        img.src = href;
        img.alt = title;
        left.innerHTML = '';
        left.appendChild(img);
    } else if (type === 'pdf') {
        var iframe = document.createElement('iframe');
        iframe.src = href;
        left.innerHTML = '';
        left.appendChild(iframe);
    } else {
        left.innerHTML = '<div class="att-overlay-placeholder">&#128196;<br>'
            + escHtml(title) + '<br><a href="' + escHtml(href)
            + '" target="_blank">Ouvrir le fichier &#8599;</a></div>';
    }

    // Droite : texte OCR
    if (ocrId) {
        var ocrEl = document.getElementById(ocrId);
        if (ocrEl) {
            var pre = document.createElement('pre');
            pre.textContent = ocrEl.textContent;
            right.innerHTML = '';
            right.appendChild(pre);
        } else {
            right.innerHTML = '<div class="att-overlay-empty">Aucun contenu extrait</div>';
        }
    } else {
        right.innerHTML = '<div class="att-overlay-empty">Aucun contenu extrait</div>';
    }

    overlay.style.display = 'flex';
    document.body.style.overflow = 'hidden';
};

window.closeAttOverlay = function() {
    document.getElementById('att-overlay').style.display = 'none';
    document.getElementById('att-overlay-left').innerHTML = '';
    document.getElementById('att-overlay-right').innerHTML = '';
    document.body.style.overflow = '';
};

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') window.closeAttOverlay();
});

// ========================================================
//  Filtre par équipement (multi-sélection)
// ========================================================

var _activeEqFilters = [];

/** Collecte tous les noms d'équipements liés à un nom donné (via inventory ID). */
function collectEqNames(eqName) {
    var names = [eqName];
    // Utilise un filter au lieu d'un sélecteur CSS vulnérable
    var allItems = Array.from(qsa('.eq-inv-clickable')).filter(function(el) {
        return el.dataset.eqName === eqName;
    });
    allItems.forEach(function(item) {
        if (item.dataset.eqGroupNames) {
            item.dataset.eqGroupNames.split('|').forEach(function(n) {
                if (names.indexOf(n) === -1) names.push(n);
            });
        }
        var linkBtn = item.querySelector('.eq-inv-link-btn');
        if (linkBtn && linkBtn.dataset.inventoryId) {
            var invId = linkBtn.dataset.inventoryId;
            qsa('.eq-inv-clickable').forEach(function(el) {
                var btn = el.querySelector('.eq-inv-link-btn');
                if (btn && btn.dataset.inventoryId === invId) {
                    var n = el.dataset.eqName;
                    if (names.indexOf(n) === -1) names.push(n);
                }
            });
        }
    });
    return names;
}

window.filterByEquipment = function(eqName) {
    clearTypeFilter();
    var idx = _activeEqFilters.indexOf(eqName);
    if (idx !== -1) _activeEqFilters.splice(idx, 1);
    else _activeEqFilters.push(eqName);

    if (_activeEqFilters.length === 0) {
        qsa('.ex-row').forEach(function(el) { el.classList.remove(HIDDEN_CLS); });
        qsa('.eq-inv-clickable').forEach(function(el) { el.classList.remove(EQ_ACTIVE_CLS); });
        document.querySelector('.search-box').value = '';
        return;
    }

    var namesToMatch = [];
    _activeEqFilters.forEach(function(f) {
        collectEqNames(f).forEach(function(n) {
            if (namesToMatch.indexOf(n) === -1) namesToMatch.push(n);
        });
    });

    qsa('.ex-row').forEach(function(el) {
        var eqData = (el.dataset.eq || '').toLowerCase();
        if (!eqData) { el.classList.add(HIDDEN_CLS); return; }
        var eqList = eqData.split('|');
        var found = false;
        for (var i = 0; i < namesToMatch.length; i++) {
            if (eqList.indexOf(namesToMatch[i]) !== -1) { found = true; break; }
        }
        el.classList.toggle(HIDDEN_CLS, !found);
    });

    qsa('.eq-inv-clickable').forEach(function(el) {
        el.classList.toggle(EQ_ACTIVE_CLS, namesToMatch.indexOf(el.dataset.eqName) !== -1);
    });
    document.querySelector('.search-box').value = '';
};

function clearEqFilter() {
    _activeEqFilters = [];
    qsa('.ex-row').forEach(function(el) { el.classList.remove(HIDDEN_CLS); });
    qsa('.eq-inv-clickable').forEach(function(el) { el.classList.remove(EQ_ACTIVE_CLS); });
}

// ========================================================
//  Liaison équipement → inventaire Django
// ========================================================

window.linkEquipment = function(eqId) {
    var linkEl = document.getElementById('eq-link-' + eqId);
    var item = linkEl.closest('.eq-inv-clickable');

    if (linkEl.classList.contains(LINKED_CLS)) {
        var current = linkEl.dataset.inventoryId || '';
        var action = prompt('Lié à inventaire Django: ' + current
            + '\nEntrez un nouvel ID ou laissez vide pour délier:', current);
        if (action === null) return;
        if (action.trim() === '') {
            linkEl.classList.remove(LINKED_CLS);
            linkEl.title = 'Lier à un item inventaire Django';
            delete linkEl.dataset.inventoryId;
            linkEl.innerHTML = '&#128279;';
        } else {
            linkEl.dataset.inventoryId = action.trim();
            linkEl.title = 'Lié: ' + action.trim();
            linkEl.innerHTML = '&#9989;';
        }
    } else {
        var id = prompt('Entrez l\'ID de l\'item dans l\'inventaire Django:');
        if (id && id.trim()) {
            linkEl.classList.add(LINKED_CLS);
            linkEl.dataset.inventoryId = id.trim();
            linkEl.title = 'Lié: ' + id.trim();
            linkEl.innerHTML = '&#9989;';
        }
    }
    regroupEquipment();
};

// ========================================================
//  Regroupement d'équipements par inventory ID
// ========================================================

function regroupEquipment() {
    // 1. Reset : tout afficher, vider les compteurs
    qsa('.eq-inv-clickable').forEach(function(el) {
        el.classList.remove(GROUPED_CLS);
        var cnt = el.querySelector('.eq-inv-count');
        if (cnt) cnt.textContent = '';
        var dateEl = el.querySelector('.eq-inv-date');
        if (dateEl && el.dataset.eqDate) {
            var parts = el.dataset.eqDate.split('-');
            if (parts.length === 3) dateEl.textContent = parts[2] + '/' + parts[1] + '/' + parts[0];
        }
    });

    // 2. Collecter par inventory ID
    var byInvId = {};
    qsa('.eq-inv-clickable').forEach(function(el) {
        var btn = el.querySelector('.eq-inv-link-btn');
        if (!btn || !btn.dataset.inventoryId) return;
        var invId = btn.dataset.inventoryId;
        if (!byInvId[invId]) byInvId[invId] = [];
        byInvId[invId].push(el);
    });

    // 3. Regrouper (masquer les doublons, afficher le compteur + bouton ✕)
    for (var invId in byInvId) {
        var group = byInvId[invId];
        if (group.length < 2) continue;

        group.sort(function(a, b) {
            return (b.dataset.eqDate || '').localeCompare(a.dataset.eqDate || '');
        });
        var leader = group[0];
        var dates = group.map(function(el) { return el.dataset.eqDate || ''; }).filter(Boolean).sort();

        // Compteur + bouton dissociation
        var cnt = leader.querySelector('.eq-inv-count');
        if (cnt) {
            cnt.innerHTML = '(' + group.length + ' mentions) '
                + '<span class="eq-unlink-btn" onclick="event.stopPropagation();unlinkGroup(\''
                + escHtml(invId) + '\')" title="Dissocier le groupe">&#10005;</span>';
        }

        // Plage de dates
        var dateEl = leader.querySelector('.eq-inv-date');
        if (dateEl && dates.length >= 2) {
            var fmtD = function(d) { var p = d.split('-'); return p[2] + '/' + p[1] + '/' + p[0]; };
            dateEl.textContent = (dates[0] === dates[dates.length - 1])
                ? fmtD(dates[dates.length - 1])
                : fmtD(dates[0]) + ' \u2192 ' + fmtD(dates[dates.length - 1]);
        }

        // Stocker les noms groupés et masquer les doublons
        var allNames = [];
        group.forEach(function(el) {
            var n = el.dataset.eqName;
            if (allNames.indexOf(n) === -1) allNames.push(n);
        });
        leader.dataset.eqGroupNames = allNames.join('|');
        for (var i = 1; i < group.length; i++) group[i].classList.add(GROUPED_CLS);
    }

    // 4. Mettre à jour les compteurs de catégorie
    qsa('.eq-inv-cat').forEach(function(catDiv) {
        var visible = catDiv.querySelectorAll('.eq-inv-clickable:not(.' + GROUPED_CLS + ')').length;
        var head = catDiv.querySelector('.eq-inv-cat-head');
        if (head) {
            var base = head.textContent.replace(/\s*\(\d+\)\s*$/, '');
            head.textContent = base + ' (' + visible + ')';
        }
    });
}

// ========================================================
//  Dissociation d'un groupe d'équipements
// ========================================================

window.unlinkGroup = function(invId) {
    if (!confirm('Dissocier tous les items liés à l\'inventaire ' + invId + ' ?')) return;
    qsa('.eq-inv-clickable').forEach(function(el) {
        var btn = el.querySelector('.eq-inv-link-btn');
        if (btn && btn.dataset.inventoryId === invId) {
            btn.classList.remove(LINKED_CLS);
            delete btn.dataset.inventoryId;
            btn.innerHTML = '&#128279;';
            btn.title = 'Lier à un item inventaire Django';
        }
    });
    regroupEquipment();
};

// Regrouper au chargement de la page
document.addEventListener('DOMContentLoaded', regroupEquipment);

})();
