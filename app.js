/**
 * Smart Review App - Vanilla JS SPA (IndexedDB + Import/Export Version)
 *
 * * 架构:
 * - App: 主应用对象，处理路由、事件委托和视图渲染。
 * - DataManager: 负责所有 localStorage 的元数据 (Metadata) CRUD。
 * - DBManager: 负责 IndexedDB 的数据库连接和图片 (Blob) CRUD。
 * - UIRenderer: 包含所有 HTML 模板字符串的函数。
 * - ModalManager: 管理模态弹窗的显示/隐藏和逻辑。
 * - ReviewEngine: 处理复习逻辑和队列生成。
 * - StatsManager: 处理统计数据计算、图表和表格渲染。
 *
 * * NEW: 导入/导出辅助函数
 * - blobToBase64(blob): 将图片 Blob 转换为 Data URL 字符串。
 * - base64ToBlob(base64): 将 Data URL 字符串转换回 Blob。
 *
 * * 导出逻辑 (App.handleExportKB):
 * 1. Deep copy 知识库元数据。
 * 2. 遍历知识点 (KP)。
 * 3. if (kp.imageId):
 * 4.   await DBManager.getImage(kp.imageId) -> blob
 * 5.   await blobToBase64(blob) -> base64
 * 6.   kp.imageData = base64 (添加新字段)
 * 7.   delete kp.imageId (删除旧字段)
 * 8. 将修改后的 kb 对象 stringify 为 JSON 并触发下载。
 *
 * * 导入逻辑 (App.handleImportFile):
 * 1. 读取并解析 .json 文件。
 * 2. 创建一个新的 kb 对象，并分配 *新* 的 kb.id。
 * 3. 遍历导入的 knowledgePoints。
 * 4. 创建一个新的 kp 对象，并分配 *新* 的 kp.id。
 * 5. if (kp.imageData):
 * 6.   base64ToBlob(kp.imageData) -> blob
 * 7.   分配一个 *新* 的 imageId。
 * 8.   await DBManager.saveImage(newImageId, blob)
 * 9.   kp.imageId = newImageId
 * 10.  delete kp.imageData
 * 11. 将 *新* 的 kp 对象添加到 *新* 的 kb 对象中。
 * 12. 将 *新* 的 kb 对象存入 DataManager。
 */

document.addEventListener('DOMContentLoaded', () => {

    // --- 0. NEW: 导入/导出辅助函数 ---

    /**
     * 将 Blob 转换为 Base64 Data URL
     * @param {Blob} blob
     * @returns {Promise<string>}
     */
    function blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = (error) => reject(error);
            reader.readAsDataURL(blob);
        });
    }

    /**
     * 将 Base64 Data URL 转换回 Blob
     * @param {string} base64
     * @returns {Blob}
     */
    function base64ToBlob(base64) {
        try {
            const parts = base64.split(';base64,');
            const contentType = parts[0].split(':')[1];
            const byteCharacters = atob(parts[1]);
            const byteNumbers = new Array(byteCharacters.length);
            for (let i = 0; i < byteCharacters.length; i++) {
                byteNumbers[i] = byteCharacters.charCodeAt(i);
            }
            const byteArray = new Uint8Array(byteNumbers);
            return new Blob([byteArray], { type: contentType });
        } catch (e) {
            console.error('Base64 转换 Blob 失败:', e);
            return null;
        }
    }

    // --- 1. IndexedDB 数据库管理器 ---
    const DBManager = {
        db: null,
        dbName: 'SmartReviewDB',
        storeName: 'imageStore',

        init() {
            return new Promise((resolve, reject) => {
                if (this.db) {
                    return resolve(this.db);
                }
                const request = indexedDB.open(this.dbName, 1);
                request.onupgradeneeded = (event) => {
                    const db = event.target.result;
                    if (!db.objectStoreNames.contains(this.storeName)) {
                        db.createObjectStore(this.storeName, { keyPath: 'id' });
                    }
                };
                request.onsuccess = (event) => {
                    this.db = event.target.result;
                    resolve(this.db);
                };
                request.onerror = (event) => {
                    console.error('IndexedDB error:', event.target.error);
                    reject('IndexedDB 数据库加载失败');
                };
            });
        },

        saveImage(id, blob) {
            return new Promise(async (resolve, reject) => {
                const db = await this.init();
                const transaction = db.transaction(this.storeName, 'readwrite');
                const store = transaction.objectStore(this.storeName);
                const request = store.put({ id, blob });
                request.onsuccess = () => resolve(id);
                request.onerror = (event) => reject('保存图片失败');
            });
        },

        getImage(id) {
            return new Promise(async (resolve, reject) => {
                if (!id) return resolve(null);
                const db = await this.init();
                const transaction = db.transaction(this.storeName, 'readonly');
                const store = transaction.objectStore(this.storeName);
                const request = store.get(id);
                request.onsuccess = (event) => {
                    resolve(event.target.result ? event.target.result.blob : null);
                };
                request.onerror = (event) => reject('读取图片失败');
            });
        },

        deleteImage(id) {
            return new Promise(async (resolve, reject) => {
                if (!id) return resolve();
                const db = await this.init();
                const transaction = db.transaction(this.storeName, 'readwrite');
                const store = transaction.objectStore(this.storeName);
                const request = store.delete(id);
                request.onsuccess = () => resolve();
                request.onerror = (event) => reject('删除图片失败');
            });
        }
    };

    // --- 2. LocalStorage 数据管理器 (元数据) ---
    const DataManager = {
        storeKey: 'smartReviewAppStore_v1',

        loadData() {
            const data = localStorage.getItem(this.storeKey);
            if (data) {
                return JSON.parse(data);
            }
            const defaultData = { knowledgeBases: [] };
            this.saveData(defaultData);
            return defaultData;
        },

        saveData(data) {
            localStorage.setItem(this.storeKey, JSON.stringify(data));
        },

        uuid() {
            return `id_${Date.now().toString(36)}_${Math.random().toString(36).substring(2, 9)}`;
        },

        getKnowledgeBases() {
            return this.loadData().knowledgeBases;
        },

        getKnowledgeBase(kbId) {
            return this.loadData().knowledgeBases.find(kb => kb.id === kbId);
        },

        addKnowledgeBase(name) {
            const data = this.loadData();
            const newKB = {
                id: this.uuid(),
                name: name,
                createdAt: new Date().toISOString(),
                knowledgePoints: []
            };
            data.knowledgeBases.push(newKB);
            this.saveData(data);
            return newKB;
        },

        async deleteKnowledgeBase(kbId) {
            const data = this.loadData();
            const kb = data.knowledgeBases.find(kb => kb.id === kbId);
            if (kb) {
                const imageIds = kb.knowledgePoints.map(kp => kp.imageId).filter(Boolean);
                try {
                    await Promise.all(imageIds.map(id => DBManager.deleteImage(id)));
                } catch (e) {
                    console.error("删除知识库图片时出错:", e);
                    ModalManager.show('删除失败', '<p>删除知识库中的图片时发生错误，但元数据仍将被删除。</p>', null, null);
                }
                data.knowledgeBases = data.knowledgeBases.filter(kb => kb.id !== kbId);
                this.saveData(data);
            }
        },

        getKnowledgePoint(kbId, kpId) {
            const kb = this.getKnowledgeBase(kbId);
            return kb ? kb.knowledgePoints.find(kp => kp.id === kpId) : null;
        },

        addKnowledgePoint(kbId, kpData) {
            const data = this.loadData();
            const kb = data.knowledgeBases.find(kb => kb.id === kbId);
            if (kb) {
                const newKP = {
                    id: this.uuid(),
                    title: kpData.title,
                    content: kpData.content,
                    imageId: kpData.imageId,
                    createdAt: new Date().toISOString(),
                    stats: { know: 0, uncertain: 0, dontKnow: 0 }
                };
                kb.knowledgePoints.push(newKP);
                this.saveData(data);
            }
        },

        updateKnowledgePoint(kbId, kpId, kpData) {
            const data = this.loadData();
            const kb = data.knowledgeBases.find(kb => kb.id === kbId);
            if (kb) {
                const kpIndex = kb.knowledgePoints.findIndex(kp => kp.id === kpId);
                if (kpIndex > -1) {
                    kb.knowledgePoints[kpIndex] = {
                        ...kb.knowledgePoints[kpIndex],
                        title: kpData.title,
                        content: kpData.content,
                        imageId: kpData.imageId,
                    };
                    this.saveData(data);
                }
            }
        },

        async deleteKnowledgePoint(kbId, kpId) {
            const data = this.loadData();
            const kb = data.knowledgeBases.find(kb => kb.id === kbId);
            if (kb) {
                const kp = kb.knowledgePoints.find(kp => kp.id === kpId);
                if (kp && kp.imageId) {
                    try {
                        await DBManager.deleteImage(kp.imageId);
                    } catch (e) {
                         console.error("删除知识点图片时出错:", e);
                         ModalManager.show('删除失败', '<p>删除知识点的图片时发生错误，但元数据仍将被删除。</p>', null, null);
                    }
                }
                kb.knowledgePoints = kb.knowledgePoints.filter(kp => kp.id !== kpId);
                this.saveData(data);
            }
        },

        updateReviewStats(kbId, kpId, status) {
            if (!['know', 'uncertain', 'dontKnow'].includes(status)) return;
            const data = this.loadData();
            const kb = data.knowledgeBases.find(kb => kb.id === kbId);
            if (kb) {
                const kp = kb.knowledgePoints.find(kp => kp.id === kpId);
                if (kp) {
                    kp.stats[status]++;
                    this.saveData(data);
                }
            }
        },

        /**
         * 清空指定知识库的所有统计数据
         * @param {string} kbId
         */
        clearKnowledgeBaseStats(kbId) {
            const data = this.loadData();
            const kb = data.knowledgeBases.find(kb => kb.id === kbId);
            if (kb) {
                kb.knowledgePoints.forEach(kp => {
                    kp.stats = { know: 0, uncertain: 0, dontKnow: 0 };
                });
                this.saveData(data);
            }
        }
    };

    // --- 3. UI 渲染器 (View Templates) ---
    const UIRenderer = {

        homePage(kbs) {
            const kbCards = kbs.length > 0
                ? kbs.map(kb => this.kbCard(kb)).join('')
                : '<p>暂无知识库。请点击右上角“创建知识库”开始。</p>';
            
            return `
                <div class="page-header">
                    <h2 class="page-header-title">我的知识库</h2>
                    <div class="page-header-actions">
                        <label for="import-file-input" class="btn btn-secondary">
                            导入知识库
                        </label>
                        <button class="btn btn-primary" data-action="show-add-kb-modal">
                            创建知识库
                        </button>
                    </div>
                </div>
                <div class="kb-grid">${kbCards}</div>
            `;
        },
        
        kbCard(kb) {
            const kpCount = kb.knowledgePoints.length;
            return `
                <div class="card">
                    <div class="card-body">
                        <h3 class="card-title" data-action="go-to-kb" data-id="${kb.id}">
                            ${this.escapeHTML(kb.name)}
                        </h3>
                        <p class="card-meta">
                            包含 ${kpCount} 个知识点
                        </p>
                    </div>
                    <div class="card-actions">
                        <button class="btn btn-danger btn-small" data-action="delete-kb" data-id="${kb.id}" data-name="${this.escapeHTML(kb.name)}">
                            删除
                        </button>
                    </div>
                </div>
            `;
        },

        kbDetailPage(kb) {
            const kpItems = kb.knowledgePoints.length > 0
                ? kb.knowledgePoints.map(kp => this.kpListItem(kp, kb.id)).join('')
                : '<p>此知识库暂无知识点。请添加一个。</p>';
            
            return `
                <div class="page-header">
                    <div>
                        <a href="#/" class="back-link">&larr; 返回主页</a>
                        <h2 class="page-header-title">${this.escapeHTML(kb.name)}</h2>
                    </div>
                    <div class="page-header-actions">
                        <button class="btn btn-secondary" data-action="export-kb" data-id="${kb.id}">
                            导出
                        </button>
                        
                        <button class="btn btn-danger" data-action="show-clear-stats-modal" data-id="${kb.id}" data-name="${this.escapeHTML(kb.name)}">
                            清空统计
                        </button>
                        
                        <button class="btn btn-secondary" data-action="show-review-options" data-id="${kb.id}">
                            开始复习
                        </button>
                        <button class="btn btn-primary" data-action="show-add-kp-modal" data-id="${kb.id}">
                            添加知识点
                        </button>
                    </div>
                </div>
                <ul class="kp-list">${kpItems}</ul>
            `;
        },

        kpListItem(kp, kbId) {
            return `
                <li class="kp-item">
                    <span class="kp-item-title">${this.escapeHTML(kp.title)}</span>
                    <div class="kp-item-actions">
                        <button class="btn btn-secondary btn-small" data-action="show-edit-kp-modal" data-kbid="${kbId}" data-kpid="${kp.id}">
                            编辑
                        </button>
                        <button class="btn btn-danger btn-small" data-action="delete-kp" data-kbid="${kbId}" data-kpid="${kp.id}">
                            删除
                        </button>
                    </div>
                </li>
            `;
        },

        reviewSession(kb, kp, sessionState) {
            const { currentIndex, totalCount, showAnswer } = sessionState;
            const contentHTML = showAnswer 
                ? this.flashcardAnswer(kp)
                : '<p style="text-align: center; color: var(--color-text-secondary);">点击显示答案</p>';
            
            const actionsHTML = showAnswer
                ? `
                <div class="review-btn-group">
                    <button class="btn btn-review btn-know" data-action="rate-kp" data-status="know">
                        我会 (${kp.stats.know})
                    </button>
                    <button class="btn btn-review btn-uncertain" data-action="rate-kp" data-status="uncertain">
                        不太会 (${kp.stats.uncertain})
                    </button>
                    <button class="btn btn-review btn-dont-know" data-action="rate-kp" data-status="dontKnow">
                        我不会 (${kp.stats.dontKnow})
                    </button>
                </div>
                `
                : `<button class="btn btn-primary btn-review" data-action="show-answer">显示答案</button>`;

            return `
                <div class="page-header">
                    <h2 class="page-header-title">复习中: ${this.escapeHTML(kb.name)}</h2>
                    <span class="page-header-meta">进度: ${currentIndex + 1} / ${totalCount}</span>
                </div>
                <div class="review-session">
                    <div class="flashcard">
                        <h3 class="flashcard-title">${this.escapeHTML(kp.title)}</h3>
                        ${contentHTML}
                    </div>
                    <div class="review-actions">
                        <button class="btn btn-secondary" data-action="go-to-kb" data-id="${kb.id}">结束复习</button>
                        ${actionsHTML}
                    </div>
                </div>
            `;
        },

        flashcardAnswer(kp) {
            const imageHTML = kp.tempImageUrl
                ? `<img src="${kp.tempImageUrl}" alt="知识点图片" class="flashcard-image">`
                : '';
            const textHTML = kp.content
                ? `<pre class="kp-content-text">${this.escapeHTML(kp.content)}</pre>`
                : '<p class="kp-content-text" style="color: var(--color-text-secondary);">(无文本内容)</p>';

            return `<div class="flashcard-answer-content">${imageHTML}${textHTML}</div>`;
        },
        
        reviewComplete(kbId) {
             return `
                <div class="review-session" style="text-align: center;">
                    <h2 class="page-header-title">复习完成！</h2>
                    <p style="margin: 20px 0;">你已完成本次复习队列中的所有知识点。</p>
                    <button class="btn btn-primary" data-action="go-to-kb" data-id="${kbId}">
                        返回知识库
                    </button>
                </div>
            `;
        },
        
        statsPage(kbs) {
            if (kbs.length === 0) {
                return `
                    <div class="page-header"><h2 class="page-header-title">数据统计</h2></div>
                    <p>请先创建至少一个知识库并添加知识点，才能查看统计数据。</p>
                `;
            }
            const options = kbs.map(kb => 
                `<option value="${kb.id}">${this.escapeHTML(kb.name)}</option>`
            ).join('');

            return `
                <div class="page-header"><h2 class="page-header-title">数据统计</h2></div>
                <div class="stats-controls">
                    <label for="stats-kb-select">选择知识库:</label>
                    <select id="stats-kb-select" data-action="select-stats-kb">${options}</select>
                </div>
                <div class="chart-container">
                    <h3 style="margin-bottom: 15px; text-align: center;">Top 15 难点知识 (按“不会”次数)</h3>
                    <canvas id="stats-chart"></canvas>
                </div>
                <div class="stats-table-container">
                    <h3 style="margin-bottom: 15px;">所有知识点详情</h3>
                    <table class="stats-table" id="stats-table">
                        <thead>
                            <tr>
                                <th data-sortable="true" data-key="title">知识点 <span class="sort-arrow"></span></th>
                                <th data-sortable="true" data-key="know">会 <span class="sort-arrow"></span></th>
                                <th data-sortable="true" data-key="uncertain">不太会 <span class="sort-arrow"></span></th>
                                <th data-sortable="true" data-key="dontKnow">不会 <span class="sort-arrow"></span></th>
                                <th data-sortable="true" data-key="ratio">“不会”比例 <span class="sort-arrow"></span></th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            `;
        },

        statsTableRows(kps) {
            return kps.map(kp => `
                <tr>
                    <td>${this.escapeHTML(kp.title)}</td>
                    <td>${kp.stats.know}</td>
                    <td>${kp.stats.uncertain}</td>
                    <td>${kp.stats.dontKnow}</td>
                    <td>${(kp.dontKnowRatio * 100).toFixed(1)}%</td>
                </tr>
            `).join('');
        },

        escapeHTML(str) {
            if (typeof str !== 'string') return '';
            return str.replace(/[&<>"']/g, m => ({'&': '&amp;','<': '&lt;','>': '&gt;','"': '&quot;',"'": '&#39;'})[m]);
        }
    };

    // --- 4. 模态弹窗管理器 ---
    const ModalManager = {
        overlay: document.getElementById('modal-overlay'),
        titleEl: document.getElementById('modal-title'),
        bodyEl: document.getElementById('modal-body'),
        cancelBtn: document.getElementById('modal-btn-cancel'),
        confirmBtn: document.getElementById('modal-btn-confirm'),
        onConfirmCallback: null,
        tempPreviewUrl: null,
        currentPasteHandler: null, // [NEW FEATURE] 引用粘贴处理器

        init() {
            this.overlay.addEventListener('click', (e) => {
                if (e.target === this.overlay) this.hide();
            });
            this.cancelBtn.addEventListener('click', () => this.hide());
            this.confirmBtn.addEventListener('click', () => {
                this.onConfirmCallback && this.onConfirmCallback();
            });
        },

        show(title, bodyHTML, confirmText = '确认', onConfirm = null) {
            this.titleEl.textContent = title;
            this.bodyEl.innerHTML = bodyHTML;
            this.confirmBtn.textContent = confirmText;
            this.onConfirmCallback = onConfirm;
            this.confirmBtn.style.display = onConfirm ? 'inline-block' : 'none';
            this.cancelBtn.style.display = onConfirm ? 'inline-block' : 'none';
            
            // NEW: 如果没有 onConfirm，隐藏取消按钮，使其成为一个“通知”
            if (!onConfirm) {
                this.cancelBtn.style.display = 'none';
                this.confirmBtn.style.display = 'inline-block';
                this.confirmBtn.textContent = confirmText || '好的';
                this.onConfirmCallback = this.hide; // 确认按钮只用于关闭
            }

            this.overlay.classList.remove('hidden');
        },

        hide() {
            this.overlay.classList.add('hidden');
            this.titleEl.textContent = '';
            this.bodyEl.innerHTML = '';
            this.onConfirmCallback = null;
            if (this.tempPreviewUrl) {
                URL.revokeObjectURL(this.tempPreviewUrl);
                this.tempPreviewUrl = null;
            }

            // [NEW FEATURE] 移除粘贴事件监听器
            if (this.currentPasteHandler) {
                document.removeEventListener('paste', this.currentPasteHandler);
                this.currentPasteHandler = null;
            }
        },

        showKBForm() {
            const title = '创建新知识库';
            const body = `
                <div class="form-group">
                    <label for="kb-name">知识库名称:</label>
                    <input type="text" id="kb-name" class="form-control" placeholder="例如：JavaScript 核心概念" required>
                </div>
            `;
            this.show(title, body, '创建', () => {
                const nameInput = document.getElementById('kb-name');
                const name = nameInput.value.trim();
                if (name) {
                    DataManager.addKnowledgeBase(name);
                    this.hide();
                    App.router();
                } else {
                    nameInput.style.borderColor = 'red';
                    this.show('输入错误', '<p>请输入知识库名称。</p>', '好的');
                }
            });
        },

        async showKPForm(kbId, kp = null) {
            const isEdit = kp !== null;
            const title = isEdit ? '编辑知识点' : '添加知识点';
            let tempImageBlob = null;
            const oldImageId = isEdit ? kp.imageId : null;
            let initialPreviewUrl = null;

            if (isEdit && kp.imageId) {
                const blob = await DBManager.getImage(kp.imageId);
                if (blob) {
                    initialPreviewUrl = URL.createObjectURL(blob);
                    this.tempPreviewUrl = initialPreviewUrl;
                }
            }
            
            const body = `
                <form id="kp-form">
                    <div class="form-group">
                        <label for="kp-title">标题 (必填):</label>
                        <input type="text" id="kp-title" class="form-control" value="${isEdit ? UIRenderer.escapeHTML(kp.title) : ''}" required>
                    </div>
                    <div class="form-group">
                        <label for="kp-content-text">内容 (文本):</label>
                        <textarea id="kp-content-text" class="form-control" placeholder="输入文本说明...">${isEdit ? UIRenderer.escapeHTML(kp.content) : ''}</textarea>
                    </div>
                    <div class="form-group">
                        <label>上传图片 (可选):</label>
                        <input type="file" id="kp-image-file" accept="image/*" class="hidden">
                        
                        <div id="kp-image-dropzone" class="dropzone"><p>点击、拖拽或粘贴 (Ctrl+V) 图片到这里</p></div>
                        
                        <div id="kp-image-preview-container" class="${initialPreviewUrl ? '' : 'hidden'}">
                            <img id="kp-image-preview" src="${initialPreviewUrl || ''}" alt="图片预览">
                            <button id="kp-remove-image" class="btn btn-danger btn-small">移除图片</button>
                        </div>
                    </div>
                </form>
            `;
            
            this.show(title, body, isEdit ? '保存更改' : '添加', async () => {
                const kpTitle = document.getElementById('kp-title').value.trim();
                const kpContent = document.getElementById('kp-content-text').value.trim();
                if (!kpTitle) {
                    this.show('输入错误', '<p>标题不能为空。</p>', '好的');
                    return;
                }
                
                let finalImageId = oldImageId;
                
                if (tempImageBlob) {
                    if (oldImageId) await DBManager.deleteImage(oldImageId);
                    finalImageId = DataManager.uuid();
                    await DBManager.saveImage(finalImageId, tempImageBlob);
                } else if (oldImageId && !document.getElementById('kp-image-preview').src) {
                    await DBManager.deleteImage(oldImageId);
                    finalImageId = null;
                }
                
                const kpData = { title: kpTitle, content: kpContent, imageId: finalImageId };
                isEdit ? DataManager.updateKnowledgePoint(kbId, kp.id, kpData) : DataManager.addKnowledgePoint(kbId, kpData);
                
                this.hide();
                App.router();
            });

            const dropzone = document.getElementById('kp-image-dropzone');
            const fileInput = document.getElementById('kp-image-file');
            const previewContainer = document.getElementById('kp-image-preview-container');
            const previewImg = document.getElementById('kp-image-preview');
            const removeBtn = document.getElementById('kp-remove-image');

            const handleFile = (file) => {
                if (!file || !file.type.startsWith('image/')) {
                    this.show('文件错误', '<p>请上传有效的图片文件。</p>', '好的');
                    return;
                }
                tempImageBlob = file;
                if (this.tempPreviewUrl) URL.revokeObjectURL(this.tempPreviewUrl);
                this.tempPreviewUrl = URL.createObjectURL(file);
                previewImg.src = this.tempPreviewUrl;
                previewContainer.classList.remove('hidden');
            };

            // [NEW FEATURE] 粘贴事件处理器
            const handlePaste = (e) => {
                // 仅当模态框内的表单处于激活状态时才处理
                if (!document.getElementById('kp-form')) return;

                const items = e.clipboardData?.items;
                if (!items) return;

                for (const item of items) {
                    if (item.type.indexOf('image') !== -1) {
                        e.preventDefault(); // 找到图片，阻止默认粘贴（例如粘贴到输入框）
                        const blob = item.getAsFile();
                        if (blob) {
                            handleFile(blob); // 复用现有的文件处理函数
                        }
                        break; // 只处理第一张图片
                    }
                }
            };

            // [NEW FEATURE] 存储处理器引用并添加监听器
            this.currentPasteHandler = handlePaste;
            document.addEventListener('paste', this.currentPasteHandler);


            // --- 现有的拖拽和点击监听器 ---
            dropzone.addEventListener('click', () => fileInput.click());
            fileInput.addEventListener('change', (e) => e.target.files.length && handleFile(e.target.files[0]));
            dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
            dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
            dropzone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropzone.classList.remove('dragover');
                e.dataTransfer.files.length && handleFile(e.dataTransfer.files[0]);
            });
            removeBtn.addEventListener('click', (e) => {
                e.preventDefault();
                tempImageBlob = null;
                previewImg.src = '';
                fileInput.value = ''; 
                previewContainer.classList.add('hidden');
            });
        },

        showReviewOptions(kb) {
            if (kb.knowledgePoints.length === 0) {
                this.show('无法复习', '<p>该知识库中没有知识点，请先添加。</p>', '好的');
                return;
            }
            const body = `
                <div class="form-group">
                    <label for="review-type">选择复习模式:</label>
                    <select id="review-type" class="form-control">
                        <option value="random">随机复习</option>
                        <option value="smart-dontknow">智能复习 (按“不会”次数)</option>
                        <option value="smart-ratio">智能复习 (按“不会”比例)</option>
                    </select>
                </div>
                <div class="form-group" id="review-count-group">
                    <label for="review-count">复习数量 (N):</label>
                    <input type="number" id="review-count" class="form-control" value="${Math.min(10, kb.knowledgePoints.length)}" min="1" max="${kb.knowledgePoints.length}">
                </div>
            `;
            this.show('开始复习', body, '开始', () => {
                const type = document.getElementById('review-type').value;
                const countInput = document.getElementById('review-count');
                const N = type === 'random' ? parseInt(countInput.value, 10) : kb.knowledgePoints.length;
                if (isNaN(N) || N < 1) {
                    this.show('输入错误', '<p>请输入有效的数量。</p>', '好的');
                    return;
                }
                ReviewEngine.startReview(kb.id, type, N);
                this.hide();
            });
            document.getElementById('review-type').addEventListener('change', e => {
                document.getElementById('review-count-group').classList.toggle('hidden', e.target.value !== 'random');
            });
        }
    };

    // --- 5. 复习引擎 ---
    const ReviewEngine = {
        currentQueue: [],
        currentIndex: 0,
        kbId: null,
        currentTempImageUrl: null, 

        startReview(kbId, type, N) {
            const kb = DataManager.getKnowledgeBase(kbId);
            if (!kb) return;
            let kps = [...kb.knowledgePoints];
            if (type === 'random') {
                for (let i = kps.length - 1; i > 0; i--) {
                    const j = Math.floor(Math.random() * (i + 1));
                    [kps[i], kps[j]] = [kps[j], kps[i]];
                }
                this.currentQueue = kps.slice(0, N);
            } else {
                kps.sort((a, b) => {
                    if (type === 'smart-dontknow') return b.stats.dontKnow - a.stats.dontKnow;
                    const ratioA = a.stats.dontKnow / (a.stats.know + a.stats.uncertain + a.stats.dontKnow + 1e-6);
                    const ratioB = b.stats.dontKnow / (b.stats.know + b.stats.uncertain + b.stats.dontKnow + 1e-6);
                    return ratioB - ratioA;
                });
                this.currentQueue = kps;
            }
            this.currentIndex = 0;
            this.kbId = kbId;
            App.renderReviewPage(false);
        },

        getCurrentKP() {
            return this.currentQueue[this.currentIndex];
        },
        
        getSessionState() {
             return { currentIndex: this.currentIndex, totalCount: this.currentQueue.length };
        },

        async next(status) {
            if (this.currentTempImageUrl) {
                URL.revokeObjectURL(this.currentTempImageUrl);
                this.currentTempImageUrl = null;
            }
            const currentKP = this.getCurrentKP();
            if (status) {
                DataManager.updateReviewStats(this.kbId, currentKP.id, status);
            }
            this.currentIndex++;
            if (this.currentIndex >= this.currentQueue.length) {
                App.renderReviewCompletePage();
            } else {
                await App.renderReviewPage(false);
            }
        }
    };

    // --- 6. 统计管理器 ---
    const StatsManager = {
        chartInstance: null,
        currentTableData: [],
        currentSort: { key: 'title', asc: true },
        
        getAllStats(kbId) {
            const kb = DataManager.getKnowledgeBase(kbId);
            if (!kb) return [];
            return kb.knowledgePoints.map(kp => {
                const total = kp.stats.know + kp.stats.uncertain + kp.stats.dontKnow;
                return { ...kp, dontKnowRatio: total === 0 ? 0 : kp.stats.dontKnow / total };
            });
        },

        renderChart(kbId) {
            const ctx = document.getElementById('stats-chart');
            if (!ctx) return;
            const statsData = this.getAllStats(kbId);
            statsData.sort((a, b) => b.stats.dontKnow - a.stats.dontKnow);
            const top15 = statsData.slice(0, 15).reverse();
            const labels = top15.map(kp => kp.title.length > 20 ? kp.title.substring(0, 20) + '...' : kp.title);
            const data = top15.map(kp => kp.stats.dontKnow);

            if (this.chartInstance) this.chartInstance.destroy();
            if (typeof Chart === 'undefined') {
                console.error('Chart.js 未加载');
                ctx.parentElement.innerHTML = '<p style="color: red;">图表库 Chart.js 加载失败。</p>';
                return;
            }
            this.chartInstance = new Chart(ctx.getContext('2d'), {
                type: 'bar',
                data: { labels, datasets: [{ label: '“不会”次数', data, backgroundColor: 'rgba(208, 2, 27, 0.6)', borderColor: 'rgba(208, 2, 27, 1)', borderWidth: 1 }] },
                options: { indexAxis: 'y', responsive: true, plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true } } }
            });
        },

        renderTable(kbId) {
            this.currentTableData = this.getAllStats(kbId);
            this.currentSort = { key: 'dontKnow', asc: false };
            this.sortAndDisplayTable();
            this.setupTableSorting();
        },
        
        setupTableSorting() {
            document.querySelectorAll('#stats-table th[data-sortable="true"]').forEach(th => {
                th.removeEventListener('click', this.handleSortClick);
                th.addEventListener('click', this.handleSortClick.bind(this, th.dataset.key));
            });
        },
        
        handleSortClick(key) {
            if (this.currentSort.key === key) this.currentSort.asc = !this.currentSort.asc;
            else { this.currentSort.key = key; this.currentSort.asc = true; }
            this.sortAndDisplayTable();
        },

        sortAndDisplayTable() {
            const { key, asc } = this.currentSort;
            this.currentTableData.sort((a, b) => {
                let valA, valB;
                switch(key) {
                    case 'title': valA = a.title.toLowerCase(); valB = b.title.toLowerCase(); break;
                    case 'know': valA = a.stats.know; valB = b.stats.know; break;
                    case 'uncertain': valA = a.stats.uncertain; valB = b.stats.uncertain; break;
                    case 'dontKnow': valA = a.stats.dontKnow; valB = b.stats.dontKnow; break;
                    case 'ratio': valA = a.dontKnowRatio; valB = b.dontKnowRatio; break;
                    default: valA = 0; valB = 0;
                }
                if (valA < valB) return asc ? -1 : 1;
                if (valA > valB) return asc ? 1 : -1;
                return 0;
            });
            
            document.querySelectorAll('#stats-table th[data-sortable="true"]').forEach(th => {
                th.classList.remove('sort-asc', 'sort-desc');
                if (th.dataset.key === key) th.classList.add(asc ? 'sort-asc' : 'sort-desc');
            });
            
            const tbody = document.querySelector('#stats-table tbody');
            if (tbody) tbody.innerHTML = UIRenderer.statsTableRows(this.currentTableData);
        }
    };

    // --- 7. 主应用 (App Controller) ---
    const App = {
        mainContent: document.getElementById('main-content'),
        importFileInput: document.getElementById('import-file-input'),

        async init() {
            try {
                await DBManager.init();
            } catch (e) {
                this.mainContent.innerHTML = `<p style="color: red; padding: 20px;">${UIRenderer.escapeHTML(e)}</p>`;
                return;
            }
            ModalManager.init();
            this.mainContent.addEventListener('click', this.handleMainContentClick.bind(this));
            // NEW: 监听文件导入
            this.importFileInput.addEventListener('change', this.handleImportFile.bind(this));
            window.addEventListener('hashchange', this.router.bind(this));
            this.router();
            this.updateNavLinks();
        },

        async router() {
            if (ReviewEngine.currentTempImageUrl) {
                URL.revokeObjectURL(ReviewEngine.currentTempImageUrl);
                ReviewEngine.currentTempImageUrl = null;
            }
            const hash = window.location.hash;
            if (hash.startsWith('#/kb/')) await this.renderKBDetailPage(hash.substring(5));
            else if (hash === '#/stats') await this.renderStatsPage();
            else await this.renderHomePage();
            this.updateNavLinks();
        },
        
        updateNavLinks() {
            const hash = window.location.hash || '#/';
            document.querySelectorAll('.nav-link').forEach(link => {
                link.getAttribute('href') === hash ? link.classList.add('active') : link.classList.remove('active');
            });
        },

        async renderHomePage() {
            const kbs = DataManager.getKnowledgeBases();
            this.mainContent.innerHTML = UIRenderer.homePage(kbs);
        },
        
        async renderKBDetailPage(kbId) {
            const kb = DataManager.getKnowledgeBase(kbId);
            if (kb) this.mainContent.innerHTML = UIRenderer.kbDetailPage(kb);
            else window.location.hash = '#/';
        },
        
        async renderReviewPage(showAnswer) {
            const kb = DataManager.getKnowledgeBase(ReviewEngine.kbId);
            const kp = ReviewEngine.getCurrentKP();
            let tempImageUrl = null;
            if (kp.imageId) {
                const blob = await DBManager.getImage(kp.imageId);
                if (blob) {
                    tempImageUrl = URL.createObjectURL(blob);
                    ReviewEngine.currentTempImageUrl = tempImageUrl;
                }
            }
            const kpWithUrl = { ...kp, tempImageUrl };
            const state = { ...ReviewEngine.getSessionState(), showAnswer };
            this.mainContent.innerHTML = UIRenderer.reviewSession(kb, kpWithUrl, state);
        },
        
        renderReviewCompletePage() {
            this.mainContent.innerHTML = UIRenderer.reviewComplete(ReviewEngine.kbId);
            ReviewEngine.currentQueue = [];
            ReviewEngine.currentIndex = 0;
            // ReviewEngine.kbId = null; // [BUG FIX] 已移除此行
        },

        async renderStatsPage() {
            const kbs = DataManager.getKnowledgeBases();
            this.mainContent.innerHTML = UIRenderer.statsPage(kbs);
            if (kbs.length > 0) this.updateStatsView(kbs[0].id);
        },
        
        updateStatsView(kbId) {
            StatsManager.renderChart(kbId);
            StatsManager.renderTable(kbId);
        },

        /**
         * 主事件委托 (Async)
         */
        async handleMainContentClick(e) {
            const target = e.target.closest('[data-action]');
            if (!target) return;
            
            const action = target.dataset.action;
            const id = target.dataset.id;
            const kbId = target.dataset.kbid;
            const kpId = target.dataset.kpid;

            switch(action) {
                /**
                 * [BUG FIX]
                 * 修复了在复习完成页面点击“返回知识库”无效的问题。
                 */
                case 'go-to-kb':
                    if (window.location.hash === `#/kb/${id}`) {
                        await this.renderKBDetailPage(id);
                    } else {
                        window.location.hash = `#/kb/${id}`;
                    }
                    break;
                    
                case 'show-add-kb-modal': ModalManager.showKBForm(); break;
                
                case 'delete-kb':
                    ModalManager.show(
                        '确认删除',
                        `<p>确定要删除知识库 "<strong>${UIRenderer.escapeHTML(target.dataset.name)}</strong>" 吗？</p><p style="color:var(--color-dont-know);">此操作不可逆，将删除其中所有的知识点和图片。</p>`,
                        '确认删除',
                        async () => { await DataManager.deleteKnowledgeBase(id); this.router(); }
                    );
                    break;
                case 'show-add-kp-modal': await ModalManager.showKPForm(id); break;
                case 'show-edit-kp-modal':
                    const kp = DataManager.getKnowledgePoint(kbId, kpId);
                    if (kp) await ModalManager.showKPForm(kbId, kp);
                    break;
                case 'delete-kp':
                     ModalManager.show(
                        '确认删除', '<p>确定要删除这个知识点吗？</p>', '确认删除',
                        async () => { await DataManager.deleteKnowledgePoint(kbId, kpId); this.router(); }
                    );
                    break;
                case 'show-review-options':
                    const kb = DataManager.getKnowledgeBase(id);
                    if (kb) ModalManager.showReviewOptions(kb);
                    break;
                
                /**
                 * 处理清空统计按钮点击
                 */
                case 'show-clear-stats-modal':
                    ModalManager.show(
                        '确认清空统计',
                        `<p>确定要清空 "<strong>${UIRenderer.escapeHTML(target.dataset.name)}</strong>" 知识库中所有知识点的复习统计吗？</p><p>(“会”、“不太会”、“不会”的次数将全部归零)。</p><p style="color:var(--color-dont-know);">此操作不可逆。</p>`,
                        '确认清空',
                        () => { 
                            DataManager.clearKnowledgeBaseStats(id);
                            ModalManager.show('清空成功', '<p>统计数据已重置。</p>', '好的');
                        }
                    );
                    break;

                case 'show-answer': await this.renderReviewPage(true); break;
                case 'rate-kp': await ReviewEngine.next(target.dataset.status); break;
                case 'select-stats-kb': this.updateStatsView(target.value); break;
                // NEW: 导出
                case 'export-kb': await this.handleExportKB(id); break;
            }
        },

        // --- NEW: 导入/导出处理器 ---

        /**
         * NEW: 处理知识库导出
         * @param {string} kbId
         */
        async handleExportKB(kbId) {
            ModalManager.show('正在导出...', '<p>正在打包您的知识库（包括图片），请稍候...</p>', null);
            
            try {
                const kb = DataManager.getKnowledgeBase(kbId);
                // 深度拷贝，防止修改原始数据
                const exportData = JSON.parse(JSON.stringify(kb)); 
                
                for (const kp of exportData.knowledgePoints) {
                    if (kp.imageId) {
                        const blob = await DBManager.getImage(kp.imageId);
                        if (blob) {
                            kp.imageData = await blobToBase64(blob); // 添加 Base64
                        }
                        delete kp.imageId; // 移除 ID
                    }
                }
                
                const jsonString = JSON.stringify(exportData, null, 2);
                const blob = new Blob([jsonString], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `${exportData.name}.json`;
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
                URL.revokeObjectURL(url);
                
                ModalManager.hide();
                
            } catch (e) {
                console.error('导出失败:', e);
                ModalManager.show('导出失败', `<p>发生错误: ${e.message}</p>`, '好的');
            }
        },

        /**
         * NEW: 处理文件导入
         * @param {Event} event
         */
        async handleImportFile(event) {
            const file = event.target.files[0];
            if (!file) return;

            ModalManager.show('正在导入...', '<p>正在解析 .json 文件并导入图片...</p>', null);

            try {
                const fileContent = await file.text();
                const importData = JSON.parse(fileContent);

                if (!importData.name || !Array.isArray(importData.knowledgePoints)) {
                    throw new Error('文件格式无效，缺少 "name" 或 "knowledgePoints" 字段。');
                }

                // 1. 创建新的知识库，分配新 ID
                const newKB = {
                    ...importData,
                    id: DataManager.uuid(), // 关键：分配新 ID
                    knowledgePoints: []
                };

                // 2. 遍历导入的知识点
                for (const kp of importData.knowledgePoints) {
                    const newKP = {
                        ...kp,
                        id: Data.uuid(), // 关键：分配新 ID
                        imageId: null
                    };

                    // 3. 如果有图片数据，转换并存入 DB
                    if (kp.imageData) {
                        const blob = base64ToBlob(kp.imageData);
                        if (blob) {
                            const newImageId = DataManager.uuid(); // 关键：分配新 ID
                            await DBManager.saveImage(newImageId, blob);
                            newKP.imageId = newImageId;
                        }
                    }
                    delete newKP.imageData; // 清理
                    newKB.knowledgePoints.push(newKP);
                }

                // 4. 将新知识库存入 localStorage
                const data = DataManager.loadData();
                data.knowledgeBases.push(newKB);
                DataManager.saveData(data);
                
                ModalManager.hide();
                ModalManager.show('导入成功', `<p>知识库 "<strong>${UIRenderer.escapeHTML(newKB.name)}</strong>" 已成功导入。</p>`, '好的');
                this.router(); // 刷新主页

            } catch (e) {
                console.error('导入失败:', e);
                ModalManager.show('导入失败', `<p>发生错误: ${e.message}</p>`, '好的');
            } finally {
                // 清空 input，以便下次还能选择同名文件
                event.target.value = null;
            }
        }
    };

    // --- 启动应用 ---
    App.init();

});