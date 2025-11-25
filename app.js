/**
 * 大学复习酱 (Smart Review App) - v3.1 Feynman Feature Integration
 * * v3.1 新增功能:
 * 1. 费曼技巧 (Feynman Quiz): 在复习时点击按钮，AI 针对当前知识点出题。
 * 2. 交互式答题 UI: 自动判断对错并展示解析。
 */

document.addEventListener('DOMContentLoaded', () => {

    // --- 配置: 后端 API 地址 ---
    const API_CONFIG = {
        BASE_URL: 'http://127.0.0.1:5000',
        GENERATE_ENDPOINT: '/api/generate_kb',
        FEYNMAN_ENDPOINT: '/api/feynman' // 新增: 费曼出题接口
    };

    // --- 0. 导入/导出辅助函数 (保持不变) ---
    function blobToBase64(blob) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = (error) => reject(error);
            reader.readAsDataURL(blob);
        });
    }

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

    // --- 1. IndexedDB 数据库管理器 (保持不变) ---
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
                try {
                    const db = await this.init();
                    const transaction = db.transaction(this.storeName, 'readwrite');
                    const store = transaction.objectStore(this.storeName);
                    const request = store.put({ id, blob });
                    request.onsuccess = () => resolve(id);
                    request.onerror = (event) => reject('保存图片失败');
                } catch (e) { reject(e); }
            });
        },

        getImage(id) {
            return new Promise(async (resolve, reject) => {
                if (!id) return resolve(null);
                try {
                    const db = await this.init();
                    const transaction = db.transaction(this.storeName, 'readonly');
                    const store = transaction.objectStore(this.storeName);
                    const request = store.get(id);
                    request.onsuccess = (event) => {
                        resolve(event.target.result ? event.target.result.blob : null);
                    };
                    request.onerror = (event) => reject('读取图片失败');
                } catch (e) { reject(e); }
            });
        },

        deleteImage(id) {
            return new Promise(async (resolve, reject) => {
                if (!id) return resolve();
                try {
                    const db = await this.init();
                    const transaction = db.transaction(this.storeName, 'readwrite');
                    const store = transaction.objectStore(this.storeName);
                    const request = store.delete(id);
                    request.onsuccess = () => resolve();
                    request.onerror = (event) => reject('删除图片失败');
                } catch (e) { reject(e); }
            });
        }
    };

    // --- 2. 键位与配置管理器 (保持不变) ---
    const ConfigManager = {
        keybindStoreKey: 'smartReviewKeybinds_v1' ,
        tokenStoreKey: 'smartReviewToken_v1' ,
        
        defaultKeys : {
            showAnswer: 'ArrowUp' ,
            know: 'ArrowLeft' ,
            uncertain: 'ArrowDown' ,
            dontKnow: 'ArrowRight'
        },
        
        getKeybinds()  {
            const data = localStorage.getItem(this .keybindStoreKey);
            return  data ? { ...this.defaultKeys, ...JSON.parse(data) } : { ...this.defaultKeys };
        },
        
        saveKeybinds(keybinds)  {
            localStorage.setItem(this.keybindStoreKey, JSON .stringify(keybinds));
        },

        getToken()  {
            return localStorage.getItem(this.tokenStoreKey) || '' ;
        },

        saveToken(token)  {
            localStorage.setItem(this .tokenStoreKey, token.trim());
        }
    };

    // --- 3. LocalStorage 数据管理器 (保持不变) ---
    const DataManager = {
        storeKey: 'smartReviewAppStore_v1',

        _getNewStatsObject(oldStats = {}) {
            return {
                know: (oldStats && typeof oldStats.know === 'number') ? oldStats.know : 0,
                uncertain: (oldStats && typeof oldStats.uncertain === 'number') ? oldStats.uncertain : 0,
                dontKnow: (oldStats && typeof oldStats.dontKnow === 'number') ? oldStats.dontKnow : 0,
                last_review: oldStats ? oldStats.last_review : null
            };
        },

        loadData() {
            const dataStr = localStorage.getItem(this.storeKey);
            let data;
            if (dataStr) {
                try {
                    data = JSON.parse(dataStr);
                } catch (e) {
                    console.error("数据解析失败，重置数据", e);
                    data = { knowledgeBases: [] };
                }
            } else {
                data = { knowledgeBases: [] };
                this.saveData(data);
                return data;
            }

            let needsSave = false;
            if (data.knowledgeBases && Array.isArray(data.knowledgeBases)) {
                for (const kb of data.knowledgeBases) {
                    if (kb.knowledgePoints && !kb.nodes) {
                        kb.nodes = kb.knowledgePoints; 
                        delete kb.knowledgePoints;
                        if (!kb.edges) kb.edges = [];
                        if (!kb.graph_metadata) { 
                            kb.graph_metadata = {
                                name: kb.name,
                                createdAt: kb.createdAt,
                                schema_version: "v1.0-graph (migrated)"
                            };
                        }
                        needsSave = true;
                    }
                    if (kb.nodes) {
                         for (const node of kb.nodes) {
                            if (!node.stats) {
                                node.stats = this._getNewStatsObject();
                                needsSave = true;
                            }
                        }
                    }
                }
            }

            if (needsSave) {
                this.saveData(data);
            }
            return data;
        },

        saveData(data) {
            try {
                localStorage.setItem(this.storeKey, JSON.stringify(data));
            } catch (e) {
                if (e.name === 'QuotaExceededError') {
                    alert('存储空间已满！请导出数据并清理部分旧知识库。');
                } else {
                    console.error('保存数据失败:', e);
                }
            }
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

        incrementNodeStat(kbId, nodeId, status) {
            const data = this.loadData();
            const kb = data.knowledgeBases.find(k => k.id === kbId);
            if (kb && kb.nodes) {
                const node = kb.nodes.find(n => n.id === nodeId);
                if (node) {
                    if (!node.stats) node.stats = this._getNewStatsObject();
                    const currentVal = parseInt(node.stats[status] || 0, 10);
                    node.stats[status] = currentVal + 1;
                    node.stats.last_review = new Date().toISOString();
                    this.saveData(data);
                    return node.stats;
                }
            }
            return null;
        },

        addKnowledgeBase(name) {
            const data = this.loadData();
            const newKB = {
                id: this.uuid(),
                name: name,
                createdAt: new Date().toISOString(),
                graph_metadata: {
                    name: name,
                    createdAt: new Date().toISOString(),
                    schema_version: "v1.0-graph"
                },
                nodes: [],
                edges: []
            };
            data.knowledgeBases.push(newKB);
            this.saveData(data);
            return newKB;
        },

        saveFullKnowledgeBase(kbObject) {
            const data = this.loadData();
            data.knowledgeBases.push(kbObject);
            this.saveData(data);
        },

        updateKnowledgeBaseName(kbId, newName) {
            const data = this.loadData();
            const kb = data.knowledgeBases.find(kb => kb.id === kbId);
            if (kb) {
                kb.name = newName;
                if (kb.graph_metadata) {
                    kb.graph_metadata.name = newName;
                }
                this.saveData(data);
            }
        },

        async deleteKnowledgeBase(kbId) {
            const data = this.loadData();
            const kb = data.knowledgeBases.find(kb => kb.id === kbId);
            if (kb) {
                const imageIds = kb.nodes.map(node => node.imageId).filter(Boolean);
                try {
                    await Promise.all(imageIds.map(id => DBManager.deleteImage(id)));
                } catch (e) {
                    console.error("删除知识库图片时出错:", e);
                }
                data.knowledgeBases = data.knowledgeBases.filter(kb => kb.id !== kbId);
                this.saveData(data);
            }
        },

        getNode(kbId, nodeId) {
            const kb = this.getKnowledgeBase(kbId);
            return kb ? kb.nodes.find(node => node.id === nodeId) : null;
        },

        addNode(kbId, nodeData) {
            const data = this.loadData();
            const kb = data.knowledgeBases.find(kb => kb.id === kbId);
            if (kb) {
                const newNode = {
                    id: this.uuid(),
                    title: nodeData.title,
                    content: nodeData.content,
                    imageId: nodeData.imageId,
                    createdAt: new Date().toISOString(),
                    stats: this._getNewStatsObject(),
                    type: nodeData.type || "GENERAL",
                    source_ref: "manual_entry"
                };
                kb.nodes.push(newNode);
                this.saveData(data);
            }
        },

        updateNode(kbId, nodeId, nodeData) {
            const data = this.loadData();
            const kb = data.knowledgeBases.find(kb => kb.id === kbId);
            if (kb) {
                const nodeIndex = kb.nodes.findIndex(node => node.id === nodeId);
                if (nodeIndex > -1) {
                    const oldStats = kb.nodes[nodeIndex].stats;
                    kb.nodes[nodeIndex] = {
                        ...kb.nodes[nodeIndex],
                        title: nodeData.title,
                        content: nodeData.content,
                        imageId: nodeData.imageId,
                        stats: oldStats || this._getNewStatsObject()
                    };
                    this.saveData(data);
                }
            }
        },

        async deleteNode(kbId, nodeId) {
            const data = this.loadData();
            const kb = data.knowledgeBases.find(kb => kb.id === kbId);
            if (kb) {
                const node = kb.nodes.find(node => node.id === nodeId);
                if (node && node.imageId) {
                    try {
                        await DBManager.deleteImage(node.imageId);
                    } catch (e) { console.error(e); }
                }
                
                kb.nodes = kb.nodes.filter(node => node.id !== nodeId);
                if (kb.edges) {
                    kb.edges = kb.edges.filter(edge => edge.source !== nodeId && edge.target !== nodeId);
                }
                this.saveData(data);
            }
        },

        clearKnowledgeBaseStats(kbId) {
            const data = this.loadData();
            const kb = data.knowledgeBases.find(kb => kb.id === kbId);
            if (kb) {
                kb.nodes.forEach(node => {
                    node.stats = this._getNewStatsObject();
                });
                this.saveData(data);
            }
        }
    };

    // --- 4. UI 渲染器 (更新) ---
    const UIRenderer = {

        injectGraphStyles() {
            const styleId = 'graph-review-styles';
            if (document.getElementById(styleId)) return;

            const css = `
                .review-grid { display: grid; grid-template-columns: 1fr 2fr 1fr; gap: 20px; max-width: 1200px; margin: 0 auto; }
                .focus-card-panel { max-width: 100%; margin: 0; }
                .context-panel { background-color: var(--color-card); border-radius: var(--border-radius); box-shadow: var(--shadow-sm); padding: 20px; align-self: start; }
                .context-panel h4 { color: var(--color-primary); border-bottom: 2px solid var(--color-bg); padding-bottom: 10px; margin-bottom: 15px; }
                .context-list { list-style: none; padding: 0; max-height: 400px; overflow-y: auto; }
                .context-item { font-size: 14px; padding: 8px 0; border-bottom: 1px solid var(--color-bg); color: var(--color-text-secondary); }
                .context-item:last-child { border-bottom: none; }
                .loading-overlay {
                    position: fixed; top: 0; left: 0; width: 100%; height: 100%;
                    background: rgba(255, 255, 255, 0.9); z-index: 2000;
                    display: flex; flex-direction: column; justify-content: center; align-items: center;
                }
                .spinner {
                    width: 50px; height: 50px; border: 5px solid #f3f3f3;
                    border-top: 5px solid var(--color-primary); border-radius: 50%;
                    animation: spin 1s linear infinite; margin-bottom: 20px;
                }
                @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                
                /* 费曼技巧 UI 样式 */
                .quiz-container { margin-top: 10px; }
                .quiz-question { font-size: 1.1em; font-weight: 600; margin-bottom: 20px; color: #333; line-height: 1.5; }
                .quiz-options { display: flex; flex-direction: column; gap: 10px; }
                .quiz-option-btn {
                    text-align: left; padding: 15px; border: 2px solid #eee; border-radius: 8px; background: #fff;
                    cursor: pointer; transition: all 0.2s; font-size: 15px;
                }
                .quiz-option-btn:hover { background-color: #f7f9fc; border-color: #d0d7de; }
                .quiz-option-btn.correct { background-color: #ecfdf5; border-color: #10b981; color: #065f46; }
                .quiz-option-btn.wrong { background-color: #fef2f2; border-color: #ef4444; color: #991b1b; }
                .quiz-analysis { margin-top: 20px; padding: 15px; background: #f8fafc; border-left: 4px solid var(--color-primary); border-radius: 4px; display: none; animation: fadeIn 0.3s; }
                .quiz-analysis h4 { margin-bottom: 5px; color: var(--color-primary); font-size: 14px; }
                .quiz-analysis p { font-size: 14px; color: #555; line-height: 1.6; }
                @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }

                @media (max-width: 960px) {
                    .review-grid { grid-template-columns: 1fr; }
                    .context-panel { display: none; }
                }
            `;
            
            const style = document.createElement('style');
            style.id = styleId;
            style.type = 'text/css';
            style.appendChild(document.createTextNode(css));
            document.head.appendChild(style);
        },

        homePage(kbs) {
            const kbCards = kbs.length > 0
                ? kbs.map(kb => this.kbCard(kb)).join('')
                : '<p>暂无知识库。您可以手动创建，或使用 AI 自动生成。</p>';
            
            return `
                <div class="page-header">
                    <h2 class="page-header-title">我的知识库</h2>
                    <div class="page-header-actions">
                        <button class="btn btn-primary" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border:none;" data-action="show-ai-modal">
                            ✨ AI 生成知识库
                        </button>
                        <label for="import-file-input" class="btn btn-secondary">
                            导入 JSON
                        </label>
                        <button class="btn btn-primary" data-action="show-add-kb-modal">
                            手动创建
                        </button>
                    </div>
                </div>
                <div class="kb-grid">${kbCards}</div>
            `;
        },
        
        kbCard(kb) {
            const nodeCount = kb.nodes ? kb.nodes.length : 0;
            return `
                <div class="card">
                    <div class="card-body">
                        <h3 class="card-title" data-action="go-to-kb" data-id="${kb.id}" title="左键点击进入，右键点击可重命名">
                            ${this.escapeHTML(kb.name)}
                        </h3>
                        <p class="card-meta">
                            包含 ${nodeCount} 个知识点
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
            const nodeItems = kb.nodes.length > 0
                ? kb.nodes.map(node => this.nodeListItem(node, kb.id)).join('')
                : '<p>此知识库暂无知识点。</p>';
            
            return `
                <div class="page-header">
                    <div>
                        <a href="#/" class="back-link">&larr; 返回主页</a>
                        <h2 class="page-header-title">${this.escapeHTML(kb.name)}</h2>
                    </div>
                    <div class="page-header-actions">
                        <button class="btn btn-secondary" data-action="export-kb" data-id="${kb.id}">
                            导出 JSON
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
                <ul class="kp-list">${nodeItems}</ul>
            `;
        },

        nodeListItem(node, kbId) {
            return `
                <li class="kp-item">
                    <span class="kp-item-title">${this.escapeHTML(node.title)}</span>
                    <div class="kp-item-actions">
                        <button class="btn btn-secondary btn-small" data-action="show-edit-kp-modal" data-kbid="${kbId}" data-kpid="${node.id}">
                            编辑
                        </button>
                        <button class="btn btn-danger btn-small" data-action="delete-kp" data-kbid="${kbId}" data-kpid="${node.id}">
                            删除
                        </button>
                    </div>
                </li>
            `;
        },

        reviewSession(kb, node, context, sessionState) {
            this.injectGraphStyles(); 
            
            const { currentIndex, totalCount, showAnswer } = sessionState;
            const contentHTML = showAnswer 
                ? this.flashcardAnswer(node)
                : '<p style="text-align: center; color: var(--color-text-secondary);">点击或按键 (↑) 显示答案</p>';
            
            const stats = node.stats || DataManager._getNewStatsObject();

            const actionsHTML = showAnswer
                ? `
                <div class="review-btn-group">
                    <button class="btn btn-review btn-know" data-action="rate-kp" data-status="know">
                        (←) 我会 (${stats.know})
                    </button>
                    <button class="btn btn-review btn-uncertain" data-action="rate-kp" data-status="uncertain">
                        (↓) 不太会 (${stats.uncertain})
                    </button>
                    <button class="btn btn-review btn-dont-know" data-action="rate-kp" data-status="dontKnow">
                        (→) 我不会 (${stats.dontKnow})
                    </button>
                </div>
                `
                : `<button class="btn btn-primary btn-review" data-action="show-answer">显示答案 (↑)</button>`;
            
            const prereqHTML = context.prerequisites.length > 0
                ? context.prerequisites.map(n => `<li class="context-item" title="${this.escapeHTML(n.title)}">${this.escapeHTML(n.title)}</li>`).join('')
                : '<li class="context-item">无</li>';
            
            const downstreamHTML = context.downstream.length > 0
                ? context.downstream.map(n => `<li class="context-item" title="${this.escapeHTML(n.title)}">${this.escapeHTML(n.title)}</li>`).join('')
                : '<li class="context-item">无</li>';
            
            return `
                <div class="page-header">
                    <div>
                        <h2 class="page-header-title">复习中: ${this.escapeHTML(kb.name)}</h2>
                        <span class="page-header-meta">当前: ${currentIndex + 1} / 总列队: ${totalCount}</span>
                    </div>
                    <div class="page-header-actions">
                        <button class="btn btn-secondary" style="background: linear-gradient(135deg, #a8edea 0%, #fed6e3 100%); border:none; color:#333; font-weight:bold;" 
                            data-action="feynman-quiz" title="AI出题检测对该知识点的掌握情况">
                            ✨ 费曼一下
                        </button>
                        <button class="btn btn-secondary" data-action="go-to-kb" data-id="${kb.id}">结束复习</button>
                    </div>
                </div>
                
                <div class="review-grid">
                    <div class="context-panel">
                        <h4>前置依赖</h4>
                        <ul class="context-list">${prereqHTML}</ul>
                    </div>
                    
                    <div class="focus-card-panel">
                        <div class="flashcard">
                            <h3 class="flashcard-title">${this.escapeHTML(node.title)}</h3>
                            <div style="text-align:center; margin-bottom: 10px; font-weight: 500; color: var(--color-text-secondary);">
                                [上次复习: ${stats.last_review ? new Date(stats.last_review).toLocaleDateString() : '从未'}]
                            </div>
                            ${contentHTML}
                        </div>
                        <div class="review-actions">
                            ${actionsHTML}
                        </div>
                    </div>
                    
                    <div class="context-panel">
                        <h4>下游应用</h4>
                        <ul class="context-list">${downstreamHTML}</ul>
                    </div>
                </div>
            `;
        },

        flashcardAnswer(node) {
            const imageHTML = node.tempImageUrl
                ? `<img src="${node.tempImageUrl}" alt="知识点图片" class="flashcard-image">`
                : '';
            const textHTML = node.content
                ? `<pre class="kp-content-text">${this.escapeHTML(node.content)}</pre>`
                : '<p class="kp-content-text" style="color: var(--color-text-secondary);">(无文本内容)</p>';

            return `<div class="flashcard-answer-content">${imageHTML}${textHTML}</div>`;
        },
        
        reviewComplete(kbId) {
             return `
                <div class="review-session" style="text-align: center;">
                    <h2 class="page-header-title">复习完成！</h2>
                    <p style="margin: 20px 0;">你已完成本次复习队列中的所有知识点。</p>
                    <div class="review-actions" style="justify-content: center;">
                         <button class="btn btn-secondary" data-action="go-to-kb" data-id="${kbId}">
                            返回知识库
                        </button>
                        <button class="btn btn-primary" data-action="review-again">
                            按原设定再来一轮
                        </button>
                    </div>
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
                                <th data-sortable="true" data-key="ratio">不会比例 <span class="sort-arrow"></span></th>
                            </tr>
                        </thead>
                        <tbody></tbody>
                    </table>
                </div>
            `;
        },

        statsTableRows(nodes) {
            return nodes.map(node => {
                const stats = node.stats || DataManager._getNewStatsObject(); 
                return `
                    <tr>
                        <td>${this.escapeHTML(node.title)}</td>
                        <td>${stats.know}</td>
                        <td>${stats.uncertain}</td>
                        <td>${stats.dontKnow}</td>
                        <td>${(node.dontKnowRatio * 100).toFixed(1)}%</td>
                    </tr>
                `;
            }).join('');
        },

        settingsPage(currentKeys) {
            const savedToken = ConfigManager.getToken();
            return `
                <div class="page-header">
                    <h2 class="page-header-title">系统设置</h2>
                </div>
                
                <div class="form-container" style="max-width: 600px; margin: 0 auto;">
                    
                    <div class="card" style="margin-bottom: 30px; border: 1px solid #e0e0e0; box-shadow: none;">
                        <div class="card-body">
                            <h3 style="margin-bottom: 15px; font-size: 18px; color: var(--color-primary);">🤖 模型 API 配置</h3>
                            <div class="form-group">
                                <label for="api-token">API Key / Token:</label>
                                <input type="password" id="api-token" class="form-control"
                                    placeholder="sk-..."
                                    value="${this.escapeHTML(savedToken)}">
                                <p style="font-size: 12px; color: #999; margin-top: 5px;">
                                    Token 将保存在您的浏览器本地存储中，并在生成知识库时发送给后端。
                                </p>
                            </div>
                            <div style="text-align: right;">
                                <button class="btn btn-primary" data-action="save-token">保存 Token</button>
                            </div>
                        </div>
                    </div>

                    <div class="card" style="border: 1px solid #e0e0e0; box-shadow: none;">
                        <div class="card-body">
                            <h3 style="margin-bottom: 15px; font-size: 18px; color: var(--color-primary);">⌨️ 快捷键设置</h3>
                            <div class="form-group">
                                <label for="key-showAnswer">显示答案:</label>
                                <input type="text" id="key-showAnswer" class="form-control keybind-input" data-keybind="showAnswer" value="${this.escapeHTML(currentKeys.showAnswer)}" readonly style="cursor: pointer;">
                            </div>
                            <div class="form-group">
                                <label for="key-know">我会 (Know):</label>
                                <input type="text" id="key-know" class="form-control keybind-input" data-keybind="know" value="${this.escapeHTML(currentKeys.know)}" readonly style="cursor: pointer;">
                            </div>
                            <div class="form-group">
                                <label for="key-uncertain">不太会 (Uncertain):</label>
                                <input type="text" id="key-uncertain" class="form-control keybind-input" data-keybind="uncertain" value="${this.escapeHTML(currentKeys.uncertain)}" readonly style="cursor: pointer;">
                            </div>
                            <div class="form-group">
                                <label for="key-dontKnow">我不会 (Don't Know):</label>
                                <input type="text" id="key-dontKnow" class="form-control keybind-input" data-keybind="dontKnow" value="${this.escapeHTML(currentKeys.dontKnow)}" readonly style="cursor: pointer;">
                            </div>
                            <div class="page-header-actions" style="margin-top: 25px; justify-content: flex-start;">
                                <button class="btn btn-secondary" data-action="save-keybinds">
                                    保存键位
                                </button>
                                <button class="btn btn-danger btn-small" style="margin-left: auto;" data-action="reset-keybinds">
                                    恢复默认
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        },

        escapeHTML(str) {
            if (typeof str !== 'string') return '';
            return str.replace(/[&<>"']/g, m => ({'&': '&amp;','<': '&lt;','>': '&gt;','"': '&quot;',"'": '&#39;'})[m]);
        },

        showLoading(message = "正在处理...") {
            const overlay = document.createElement('div');
            overlay.className = 'loading-overlay';
            overlay.id = 'global-loading-overlay';
            overlay.innerHTML = `
                <div class="spinner"></div>
                <h3 style="color: #333; font-weight: 600;">${message}</h3>
                <p style="color: #777; margin-top: 10px;">智能体正在飞速运转...</p>
            `;
            document.body.appendChild(overlay);
        },

        hideLoading() {
            const overlay = document.getElementById('global-loading-overlay');
            if (overlay) overlay.remove();
        }
    };

    // --- 5. 模态弹窗管理器 (更新: 新增交互式 Quiz) ---
    const ModalManager = {
        overlay: document.getElementById('modal-overlay'),
        titleEl: document.getElementById('modal-title'),
        bodyEl: document.getElementById('modal-body'),
        cancelBtn: document.getElementById('modal-btn-cancel'),
        confirmBtn: document.getElementById('modal-btn-confirm'),
        onConfirmCallback: null,
        tempPreviewUrl: null,
        currentPasteHandler: null,
        uploadedFiles: [], 

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
            if (!onConfirm) {
                this.cancelBtn.style.display = 'none';
                this.confirmBtn.style.display = 'inline-block';
                this.confirmBtn.textContent = confirmText || '好的';
                this.onConfirmCallback = this.hide; 
            }
            this.overlay.classList.remove('hidden');
        },

        hide() {
            this.overlay.classList.add('hidden');
            this.titleEl.textContent = '';
            this.bodyEl.innerHTML = '';
            this.onConfirmCallback = null;
            this.uploadedFiles = [];
            if (this.tempPreviewUrl) {
                URL.revokeObjectURL(this.tempPreviewUrl);
                this.tempPreviewUrl = null;
            }
            if (this.currentPasteHandler) {
                document.removeEventListener('paste', this.currentPasteHandler);
                this.currentPasteHandler = null;
            }
        },

        // --- 新增: 交互式 Quiz 弹窗 ---
        showQuiz(quizData) {
            // 解析正确答案的索引（简单假设答案字符串包含 "A." / "B." 等前缀，或完全匹配）
            const answerStr = quizData.answer || "";
            // 简单的提取逻辑，假设选项格式是 "A. xxxx"
            
            const body = `
                <div class="quiz-container">
                    <p class="quiz-question">${UIRenderer.escapeHTML(quizData.question)}</p>
                    <div class="quiz-options">
                        ${quizData.options.map((opt, index) => `
                            <button class="quiz-option-btn" data-opt="${UIRenderer.escapeHTML(opt)}">
                                ${UIRenderer.escapeHTML(opt)}
                            </button>
                        `).join('')}
                    </div>
                    <div id="quiz-analysis-box" class="quiz-analysis">
                        <h4>💡 答案解析</h4>
                        <p>${UIRenderer.escapeHTML(quizData.analysis || "暂无解析")}</p>
                        <p style="margin-top:10px; font-weight:bold; color:var(--color-primary);">正确答案: ${UIRenderer.escapeHTML(quizData.answer)}</p>
                    </div>
                </div>
            `;

            // 展示弹窗，不需要默认的“确认”逻辑，而是自定义“关闭”
            this.show('🧠 费曼测试 (AI生成)', body, '关闭', () => this.hide());
            this.cancelBtn.style.display = 'none'; // 隐藏取消按钮

            // 绑定交互逻辑
            const btns = this.bodyEl.querySelectorAll('.quiz-option-btn');
            const analysisBox = this.bodyEl.querySelector('#quiz-analysis-box');

            btns.forEach(btn => {
                btn.addEventListener('click', () => {
                    // 防止重复点击
                    if (this.bodyEl.querySelector('.quiz-option-btn.correct') || 
                        this.bodyEl.querySelector('.quiz-option-btn.wrong')) return;

                    const selectedText = btn.dataset.opt;
                    // 简单的判断：如果选项文本包含正确答案的关键字，或者正确答案包含选项的关键字
                    // 更稳健的方式：比较首字母
                    const isCorrect = selectedText.trim() === quizData.answer.trim() || 
                                      selectedText.startsWith(quizData.answer.split('.')[0]); 

                    if (isCorrect) {
                        btn.classList.add('correct');
                    } else {
                        btn.classList.add('wrong');
                        // 找到正确的并高亮
                        btns.forEach(b => {
                            if (b.dataset.opt.trim() === quizData.answer.trim() || 
                                b.dataset.opt.startsWith(quizData.answer.split('.')[0])) {
                                b.classList.add('correct');
                            }
                        });
                    }
                    
                    // 显示解析
                    analysisBox.style.display = 'block';
                });
            });
        },

        showAIGeneratorForm() {
            const title = '✨ AI 智能生成知识库';
            const body = `
                <p style="margin-bottom:15px; color:#666;">上传您的复习资料 (PDF, PPT, Word, TXT)，AI 智能体将自动为您提取知识点并构建图谱。</p>
                <div class="form-group">
                    <label for="ai-kb-name">生成知识库名称:</label>
                    <input type="text" id="ai-kb-name" class="form-control" placeholder="例如：操作系统复习" required>
                </div>
                <div class="form-group">
                    <label>上传资料:</label>
                    <input type="file" id="ai-file-input" multiple class="hidden" accept=".pdf,.ppt,.pptx,.doc,.docx,.txt,.md">
                    <div id="ai-dropzone" class="dropzone" style="border-color: #764ba2; background: #fcfaff;">
                        <p><strong>点击选择文件</strong> 或将文件拖拽至此</p>
                        <p style="font-size:12px; color:#999;">支持: PDF, PPT, Word, TXT</p>
                    </div>
                    <ul id="ai-file-list" style="list-style:none; margin-top:10px; padding:0;"></ul>
                </div>
            `;

            this.uploadedFiles = []; 

            this.show(title, body, '开始生成', () => {
                const name = document.getElementById('ai-kb-name').value.trim();
                if (!name) {
                    alert('请输入知识库名称');
                    return;
                }
                if (this.uploadedFiles.length === 0) {
                    alert('请至少上传一个文件');
                    return;
                }
                
                App.handleAIGenerate(name, this.uploadedFiles);
                this.hide();
            });

            setTimeout(() => {
                const dropzone = document.getElementById('ai-dropzone');
                const fileInput = document.getElementById('ai-file-input');
                const fileListEl = document.getElementById('ai-file-list');

                const updateFileList = () => {
                    fileListEl.innerHTML = this.uploadedFiles.map((f, index) => `
                        <li style="background:#eee; padding:5px 10px; margin-bottom:5px; border-radius:4px; display:flex; justify-content:space-between;">
                            <span>📄 ${f.name}</span>
                            <span style="cursor:pointer; color:red;" data-index="${index}" class="remove-file">×</span>
                        </li>
                    `).join('');
                    
                    fileListEl.querySelectorAll('.remove-file').forEach(btn => {
                        btn.addEventListener('click', (e) => {
                            const idx = parseInt(e.target.dataset.index);
                            this.uploadedFiles.splice(idx, 1);
                            updateFileList();
                        });
                    });
                };

                dropzone.addEventListener('click', () => fileInput.click());
                
                fileInput.addEventListener('change', (e) => {
                    if (e.target.files.length) {
                        this.uploadedFiles = [...this.uploadedFiles, ...Array.from(e.target.files)];
                        updateFileList();
                    }
                });

                dropzone.addEventListener('dragover', (e) => { e.preventDefault(); dropzone.classList.add('dragover'); });
                dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
                dropzone.addEventListener('drop', (e) => {
                    e.preventDefault();
                    dropzone.classList.remove('dragover');
                    if (e.dataTransfer.files.length) {
                        this.uploadedFiles = [...this.uploadedFiles, ...Array.from(e.dataTransfer.files)];
                        updateFileList();
                    }
                });
            }, 100);
        },

        showKBForm() {
            const title = '创建新知识库 (手动)';
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
                }
            });
        },
        
        showRenameKBForm(kbId, oldName) {
            const title = '重命名知识库';
            const body = `
                <div class="form-group">
                    <label for="kb-rename">知识库名称:</label>
                    <input type="text" id="kb-rename" class="form-control" value="${UIRenderer.escapeHTML(oldName)}" required>
                </div>
            `;
            this.show(title, body, '保存', () => {
                const nameInput = document.getElementById('kb-rename');
                const newName = nameInput.value.trim();
                if (newName && newName !== oldName) {
                    DataManager.updateKnowledgeBaseName(kbId, newName);
                    this.hide();
                    App.router(); 
                } else if (newName === oldName) {
                    this.hide(); 
                }
            });
        },

        async showKPForm(kbId, node = null) {
            const isEdit = node !== null;
            const title = isEdit ? '编辑知识点' : '添加知识点';
            let tempImageBlob = null;
            const oldImageId = isEdit ? node.imageId : null;
            let initialPreviewUrl = null;

            if (isEdit && node.imageId) {
                const blob = await DBManager.getImage(node.imageId);
                if (blob) {
                    initialPreviewUrl = URL.createObjectURL(blob);
                    this.tempPreviewUrl = initialPreviewUrl;
                }
            }
            
            const body = `
                <form id="kp-form">
                    <div class="form-group">
                        <label for="kp-title">标题 (必填):</label>
                        <input type="text" id="kp-title" class="form-control" value="${isEdit ? UIRenderer.escapeHTML(node.title) : ''}" required>
                    </div>
                    <div class="form-group">
                        <label for="kp-content-text">内容 (文本):</label>
                        <textarea id="kp-content-text" class="form-control" placeholder="输入文本说明...">${isEdit ? UIRenderer.escapeHTML(node.content) : ''}</textarea>
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
                    alert('标题不能为空');
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
                
                const nodeData = { title: kpTitle, content: kpContent, imageId: finalImageId };
                isEdit ? DataManager.updateNode(kbId, node.id, nodeData) : DataManager.addNode(kbId, nodeData);
                this.hide();
                App.router();
            });

            // 图片处理逻辑绑定
            const dropzone = document.getElementById('kp-image-dropzone');
            const fileInput = document.getElementById('kp-image-file');
            const previewContainer = document.getElementById('kp-image-preview-container');
            const previewImg = document.getElementById('kp-image-preview');
            const removeBtn = document.getElementById('kp-remove-image');
            const handleFile = (file) => {
                if (!file || !file.type.startsWith('image/')) return;
                tempImageBlob = file;
                if (this.tempPreviewUrl) URL.revokeObjectURL(this.tempPreviewUrl);
                this.tempPreviewUrl = URL.createObjectURL(file);
                previewImg.src = this.tempPreviewUrl;
                previewContainer.classList.remove('hidden');
            };
            const handlePaste = (e) => {
                if (!document.getElementById('kp-form')) return;
                const items = e.clipboardData?.items;
                if (!items) return;
                for (const item of items) {
                    if (item.type.indexOf('image') !== -1) {
                        e.preventDefault(); 
                        const blob = item.getAsFile();
                        if (blob) handleFile(blob);
                        break; 
                    }
                }
            };
            this.currentPasteHandler = handlePaste;
            document.addEventListener('paste', this.currentPasteHandler);
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
            const totalNodes = kb.nodes.length;
            if (totalNodes === 0) {
                this.show('无法复习', '<p>该知识库中没有知识点，请先添加。</p>', '好的');
                return;
            }
            
            const defaultCount = totalNodes < 20 ? totalNodes : 20;

            const body = `
                <div class="form-group">
                    <label for="review-type">选择复习模式:</label>
                    <select id="review-type" class="form-control">
                        <option value="smart-dontknow">智能复习 (按“不会”次数)</option>
                        <option value="smart-ratio">智能复习 (按“不会”比例)</option>
                        <option value="random">随机复习</option>
                    </select>
                </div>
                <div class="form-group" id="review-count-group">
                    <label for="review-count">复习数量 (输入大于总数则复习全部):</label>
                    <input type="number" id="review-count" class="form-control" value="${defaultCount}" min="1">
                    <p style="font-size: 12px; color: #777; margin-top: 5px;">当前知识库总数: ${totalNodes}</p>
                </div>
            `;
            this.show('开始复习', body, '开始', () => {
                const type = document.getElementById('review-type').value;
                const countInput = document.getElementById('review-count');
                let N = parseInt(countInput.value, 10);
                if (isNaN(N) || N < 1) N = totalNodes;
                if (N > totalNodes) N = totalNodes; 

                ReviewEngine.startReview(kb.id, type, N);
                this.hide();
            });
        }
    };

    // --- 6. 复习引擎 (保持不变) ---
    const ReviewEngine = {
        kb: null,
        nodesMap: null,
        currentQueue: [],
        currentNode: null,
        currentTempImageUrl: null, 
        adj_forward: null,
        adj_backward: null,
        
        lastSessionConfig: null,

        startReview(kbId, type, N) {
            const kb = DataManager.getKnowledgeBase(kbId);
            if (!kb) return;
            
            this.lastSessionConfig = { kbId, type, N };
            this.kb = JSON.parse(JSON.stringify(kb));
            this.nodesMap = new Map();
            this.adj_forward = new Map();
            this.adj_backward = new Map();
            
            this.kb.nodes.forEach(node => {
                this.nodesMap.set(node.id, node);
            });
            
            (this.kb.edges || []).forEach(edge => {
                if (!this.nodesMap.has(edge.source) || !this.nodesMap.has(edge.target)) return;
                if (!this.adj_forward.has(edge.source)) this.adj_forward.set(edge.source, new Map());
                if (!this.adj_forward.get(edge.source).has(edge.relation)) this.adj_forward.get(edge.source).set(edge.relation, []);
                this.adj_forward.get(edge.source).get(edge.relation).push(edge.target);
                
                if (!this.adj_backward.has(edge.target)) this.adj_backward.set(edge.target, new Map());
                if (!this.adj_backward.get(edge.target).has(edge.relation)) this.adj_backward.get(edge.target).set(edge.relation, []);
                this.adj_backward.get(edge.target).get(edge.relation).push(edge.source);
            });
            
            let all_nodes = [...this.kb.nodes];
            
            if (type === 'smart-dontknow') {
                all_nodes.sort((a, b) => (b.stats.dontKnow || 0) - (a.stats.dontKnow || 0));
            } else if (type === 'smart-ratio') {
                const getRatio = (n) => {
                    const total = (n.stats.know || 0) + (n.stats.uncertain || 0) + (n.stats.dontKnow || 0);
                    return total === 0 ? 0 : (n.stats.dontKnow || 0) / total;
                };
                all_nodes.sort((a, b) => getRatio(b) - getRatio(a));
            } else { 
                all_nodes.sort(() => Math.random() - 0.5);
            }
            
            const safeN = Math.min(N, all_nodes.length);
            this.currentQueue = all_nodes.slice(0, safeN); 
            
            this.loadNextCard();
        },
        
        restartLastSession() {
            if (this.lastSessionConfig) {
                this.startReview(
                    this.lastSessionConfig.kbId,
                    this.lastSessionConfig.type,
                    this.lastSessionConfig.N
                );
            }
        },

        async loadNextCard() {
            if (this.currentTempImageUrl) {
                URL.revokeObjectURL(this.currentTempImageUrl);
                this.currentTempImageUrl = null;
            }

            if (this.currentQueue.length > 0) {
                this.currentNode = this.currentQueue.shift();
            } else {
                this.currentNode = null;
            }

            if (this.currentNode) {
                const nodeToLoad = this.currentNode;
                App.renderReviewPage(false); 
                
                Promise.resolve().then(async () => {
                    if (nodeToLoad.imageId) {
                        const blob = await DBManager.getImage(nodeToLoad.imageId);
                        if (blob && this.currentNode && this.currentNode.id === nodeToLoad.id) {
                            const tempImageUrl = URL.createObjectURL(blob);
                            this.currentTempImageUrl = tempImageUrl;
                            nodeToLoad.tempImageUrl = tempImageUrl; 
                        }
                    }
                }).catch(console.error);

            } else {
                App.renderReviewCompletePage();
            }
        },

        process_review_result(status) {
            if (!this.currentNode) return;
            const newStats = DataManager.incrementNodeStat(this.kb.id, this.currentNode.id, status);
            if (newStats) {
                this.currentNode.stats = newStats;
            } else {
                if (!this.currentNode.stats) this.currentNode.stats = DataManager._getNewStatsObject();
                this.currentNode.stats[status]++;
            }
        },

        getNodeContext(nodeId) {
            const context = { prerequisites: [], downstream: [] };
            const prereq_ids = this.adj_backward.get(nodeId)?.get("is_prerequisite_for") || [];
            for (const nid of prereq_ids) {
                if (this.nodesMap.has(nid)) context.prerequisites.push(this.nodesMap.get(nid));
            }
            const downstream_ids = this.adj_forward.get(nodeId)?.get("is_prerequisite_for") || [];
            for (const nid of downstream_ids) {
                if (this.nodesMap.has(nid)) context.downstream.push(this.nodesMap.get(nid));
            }
            return context;
        }
    };

    // --- 7. 统计管理器 (保持不变) ---
    const StatsManager = {
        chartInstance: null,
        currentTableData: [],
        currentSort: { key: 'title', asc: true },
        
        getAllStats(kbId) {
            const kb = DataManager.getKnowledgeBase(kbId);
            if (!kb) return [];
            return kb.nodes.map(node => {
                const stats = node.stats || DataManager._getNewStatsObject(); 
                const total = stats.know + stats.uncertain + stats.dontKnow;
                return { ...node, stats, dontKnowRatio: total === 0 ? 0 : stats.dontKnow / total };
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
                const newTh = th.cloneNode(true);
                th.parentNode.replaceChild(newTh, th);
                newTh.addEventListener('click', this.handleSortClick.bind(this, newTh.dataset.key));
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

    // --- 8. 主应用 (App Controller) ---
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
            
            const logo = document.querySelector('.logo');
            if (logo) logo.textContent = '大学复习酱 v3.0';

            UIRenderer.injectGraphStyles(); // 确保样式加载
            ModalManager.init();
            this.mainContent.addEventListener('click', this.handleMainContentClick.bind(this));
            this.mainContent.addEventListener('contextmenu', this.handleMainContentContextMenu.bind(this));
            this.importFileInput.addEventListener('change', this.handleImportFile.bind(this));
            window.addEventListener('hashchange', this.router.bind(this));
            window.addEventListener('keydown', this.handleGlobalKeydown.bind(this));
            
            this.insertSettingsLink();
            this.router();
            this.updateNavLinks();
            
            // 检测后端服务状态
            this.checkBackendStatus();
            
            // 定期保存数据
            setInterval(() => {
                try {
                    DBManager.saveAll();
                    console.log('数据已自动保存');
                } catch (error) {
                   // console.error('自动保存失败:', error);
                }
            }, 30000); 
        },
        
        async checkBackendStatus() {

            try {
                const controller = new AbortController();
                const timeoutId = setTimeout(() => controller.abort(), 3000);
                
                const response = await fetch(`${API_CONFIG.BASE_URL}/api/health`, {
                    method: 'GET',
                    signal: controller.signal
                });
                
                clearTimeout(timeoutId);
                
                if (response.ok) {
                    console.log('后端服务状态: 正常');
                    return true;
                }
            } catch (error) {
                console.warn('后端服务不可用:', error);
                // 不阻止用户使用本地功能，仅记录警告
            }
            return false;
        },

        insertSettingsLink() {
                const nav = document.querySelector('.main-nav');
                if (nav && !nav.querySelector('a[href="#/settings"]')) {
                    nav.insertAdjacentHTML('beforeend', ' <a href="#/settings" class="nav-link">系统设置</a>');
                }
            },

        async router() {
            if (ReviewEngine.currentTempImageUrl) {
                URL.revokeObjectURL(ReviewEngine.currentTempImageUrl);
                ReviewEngine.currentTempImageUrl = null;
            }
            if (ReviewEngine.kb && !window.location.hash.startsWith('#/review/')) {
                 ReviewEngine.kb = null; 
            }

            const hash = window.location.hash;
            if (hash.startsWith('#/kb/')) await this.renderKBDetailPage(hash.substring(5));
            else if (hash.startsWith('#/review/')) {
                window.location.hash = `#/kb/${hash.substring(9)}`;
            }
            else if (hash === '#/stats') await this.renderStatsPage();
            else if (hash === '#/settings') await this.renderSettingsPage();
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
            const kb = ReviewEngine.kb;
            const node = ReviewEngine.currentNode;
            if (!kb || !node) {
                if(ReviewEngine.kb) window.location.hash = `#/kb/${ReviewEngine.kb.id}`;
                else window.location.hash = '#/';
                return;
            }
            
            const nodeWithUrl = { ...node };
            if (showAnswer && !node.tempImageUrl && node.imageId) {
                 const blob = await DBManager.getImage(node.imageId);
                 if (blob) {
                    const tempImageUrl = URL.createObjectURL(blob);
                    ReviewEngine.currentTempImageUrl = tempImageUrl;
                    node.tempImageUrl = tempImageUrl;
                    nodeWithUrl.tempImageUrl = tempImageUrl;
                 }
            }

            const context = ReviewEngine.getNodeContext(node.id);
            const state = { 
                currentIndex: (kb.nodes.length - ReviewEngine.currentQueue.length - 1),
                totalCount: kb.nodes.length, 
                showAnswer 
            };
            this.mainContent.innerHTML = UIRenderer.reviewSession(kb, nodeWithUrl, context, state);
        },
        
        renderReviewCompletePage() {
            this.mainContent.innerHTML = UIRenderer.reviewComplete(ReviewEngine.kb.id);
            ReviewEngine.kb = null;
        },

        async renderStatsPage() {
            const kbs = DataManager.getKnowledgeBases();
            this.mainContent.innerHTML = UIRenderer.statsPage(kbs);
            if (kbs.length > 0) this.updateStatsView(kbs[0].id);
        },
        
        async renderSettingsPage() {
            const keys = ConfigManager.getKeybinds();
            this.mainContent.innerHTML = UIRenderer.settingsPage(keys);
            document.querySelectorAll('.keybind-input').forEach(input => {
                input.addEventListener('keydown', this.handleKeybindInput.bind(this));
            });
        },

        updateStatsView(kbId) {
            StatsManager.renderChart(kbId);
            StatsManager.renderTable(kbId);
        },

        // --- 核心逻辑: 处理 AI 生成知识库 ---
        async handleAIGenerate(name, files) {
            const apiToken = ConfigManager.getToken();
            if (!apiToken) {
                ModalManager.show('提示', '<p>请先在设置页面填写 API Token！</p>', '去设置', () => {
                    window.location.hash = '#/settings';
                });
                return;
            }
            
            UIRenderer.showLoading(`正在分析 ${files.length} 个文件，请稍候...`);
            
            try {
                const formData = new FormData();
                formData.append('kb_name', name);
                formData.append('api_token', apiToken); 
                
                files.forEach(file => {
                    formData.append('files', file);
                });

                const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.GENERATE_ENDPOINT}`, {
                    method: 'POST',
                    body: formData
                });

                if (!response.ok) {
                    const errText = await response.text();
                    throw new Error(`服务器错误 (${response.status}): ${errText}`);
                }

                const resultJSON = await response.json();
                console.log("AI 生成成功:", resultJSON);

                await this.autoImportJSON(resultJSON);

                UIRenderer.hideLoading();
                ModalManager.show('生成成功', `<p>知识库 "<strong>${UIRenderer.escapeHTML(name)}</strong>" 已成功构建并导入！</p>`, '立刻查看', () => {
                    ModalManager.hide();
                    const allKBs = DataManager.getKnowledgeBases();
                    const newKB = allKBs[allKBs.length - 1]; 
                    if (newKB) window.location.hash = `#/kb/${newKB.id}`;
                    else this.router();
                });

            } catch (error) {
                UIRenderer.hideLoading();
                console.error('AI 生成失败:', error);
                ModalManager.show('生成失败', `<p>处理过程中发生错误：</p><pre style="background:#f0f0f0; padding:10px; overflow:auto;">${UIRenderer.escapeHTML(error.message)}</pre><p>请检查 Python 后端是否已启动。</p>`, '好的');
            }
        },

        // --- 核心逻辑: 处理费曼技巧出题 (新增) ---
        async handleFeynmanQuiz() {
            if (!ReviewEngine.currentNode) return;
            
            const topic = ReviewEngine.currentNode.title;
            const content = ReviewEngine.currentNode.content || ""; // 获取知识点内容
            const apiToken = ConfigManager.getToken();
            
            if (!apiToken) {
                ModalManager.show('提示', '<p>使用费曼技巧功能需要 API Token，请先在系统设置中填写。</p>', '去设置', () => {
                    window.location.hash = '#/settings';
                });
                return;
            }

            UIRenderer.showLoading(`AI 正在为 "${topic}" 出题...`);

            try {
                const response = await fetch(`${API_CONFIG.BASE_URL}${API_CONFIG.FEYNMAN_ENDPOINT}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        topic: {
                            title: topic,
                            content: content
                        },
                        api_token: apiToken
                    })
                });

                if (!response.ok) {
                    throw new Error("API Request Failed");
                }

                const quizData = await response.json();
                UIRenderer.hideLoading();
                
                // 显示交互式答题框
                ModalManager.showQuiz(quizData);

            } catch (error) {
                UIRenderer.hideLoading();
                console.error("Feynman quiz error:", error);
                ModalManager.show('生成失败', `<p>AI 出题失败，请检查网络或后端日志。</p>`, '好的');
            }
        },

        async autoImportJSON(importData) {
            const isV2Graph = importData.graph_metadata && importData.nodes;
            let newKB;

            if (isV2Graph) {
                newKB = { 
                    ...importData, 
                    id: DataManager.uuid(), 
                    name: importData.graph_metadata.name || "AI 生成的图谱", 
                    nodes: [] 
                };
                
                const idMap = new Map();
                for (const node of importData.nodes) {
                    const oldId = node.id;
                    const newNode = { ...node, id: DataManager.uuid(), stats: DataManager._getNewStatsObject(node.stats) };
                    idMap.set(oldId, newNode.id);
                    
                    if (node.imageData) {
                        const blob = base64ToBlob(node.imageData);
                        if (blob) {
                            const newImageId = DataManager.uuid();
                            await DBManager.saveImage(newImageId, blob);
                            newNode.imageId = newImageId;
                        }
                    }
                    delete newNode.imageData; 
                    newKB.nodes.push(newNode);
                }
                newKB.edges = (importData.edges || []).filter(edge => idMap.has(edge.source) && idMap.has(edge.target)).map(edge => ({
                    ...edge, id: DataManager.uuid(), source: idMap.get(edge.source), target: idMap.get(edge.target)
                }));
            } else {
                 newKB = {
                    id: DataManager.uuid(),
                    name: importData.name || "导入数据",
                    createdAt: new Date().toISOString(),
                    graph_metadata: { name: importData.name, createdAt: new Date().toISOString(), schema_version: "v1.0-graph" },
                    nodes: [],
                    edges: []
                };
            }

            DataManager.saveFullKnowledgeBase(newKB);
        },

        async handleMainContentClick(e) {
            const target = e.target.closest('[data-action]');
            if (!target) return;
            
            const action = target.dataset.action;
            const id = target.dataset.id;
            const kbId = target.dataset.kbid;
            const kpId = target.dataset.kpid;

            switch(action) {
                case 'go-to-kb':
                    if(ReviewEngine.kb) ReviewEngine.kb = null;
                    if (window.location.hash === `#/kb/${id}`) await this.renderKBDetailPage(id);
                    else window.location.hash = `#/kb/${id}`;
                    break;
                case 'show-ai-modal': ModalManager.showAIGeneratorForm(); break; 
                case 'show-add-kb-modal': ModalManager.showKBForm(); break;
                case 'delete-kb':
                    ModalManager.show('确认删除',`<p>确定要删除知识库 "<strong>${UIRenderer.escapeHTML(target.dataset.name)}</strong>" 吗？</p><p style="color:var(--color-dont-know);">此操作不可逆。</p>`, '确认删除', async () => { await DataManager.deleteKnowledgeBase(id); this.router(); });
                    break;
                case 'show-add-kp-modal': await ModalManager.showKPForm(id); break;
                case 'show-edit-kp-modal':
                    const node = DataManager.getNode(kbId, kpId);
                    if (node) await ModalManager.showKPForm(kbId, node);
                    break;
                case 'delete-kp':
                     ModalManager.show('确认删除', '<p>确定要删除这个知识点吗？</p>', '确认删除', async () => { await DataManager.deleteNode(kbId, kpId); this.router(); });
                    break;
                case 'show-review-options':
                    const kb = DataManager.getKnowledgeBase(id);
                    if (kb) ModalManager.showReviewOptions(kb);
                    break;
                case 'show-clear-stats-modal':
                    ModalManager.show('确认清空统计', `<p>确定要清空 "<strong>${UIRenderer.escapeHTML(target.dataset.name)}</strong>" 的统计数据吗？</p>`, '确认清空', () => { DataManager.clearKnowledgeBaseStats(id); ModalManager.show('清空成功', '<p>统计数据已重置。</p>', '好的'); });
                    break;
                case 'show-answer': await this.renderReviewPage(true); break;
                case 'rate-kp': 
                    ReviewEngine.process_review_result(target.dataset.status);
                    ReviewEngine.loadNextCard(); 
                    break;
                case 'select-stats-kb': this.updateStatsView(target.value); break;
                case 'export-kb': await this.handleExportKB(id); break;
                case 'save-token':
                    const tokenInput = document.getElementById('api-token');
                    const token = tokenInput.value.trim();
                    ConfigManager.saveToken(token);
                    ModalManager.show('保存成功', '<p>API Token 已保存到本地存储。</p>', '好的');
                    break;
                case 'save-keybinds':
                    const newKeybinds = {};
                    document.querySelectorAll('.keybind-input').forEach(input => newKeybinds[input.dataset.keybind] = input.value);
                    ConfigManager.saveKeybinds(newKeybinds);
                    ModalManager.show('保存成功', '<p>快捷键设置已保存。</p>', '好的');
                    break;
                case 'reset-keybinds':
                    ConfigManager.saveKeybinds(ConfigManager.defaultKeys);
                    await this.renderSettingsPage(); 
                    break;
                case 'review-again':
                    ReviewEngine.restartLastSession();
                    break;
                // 新增: 费曼按钮处理
                case 'feynman-quiz':
                    await this.handleFeynmanQuiz();
                    break;
            }
        },

        handleMainContentContextMenu(e) {
            const target = e.target.closest('.card-title[data-action="go-to-kb"]');
            if (!target) return;
            e.preventDefault(); 
            const kbId = target.dataset.id;
            const oldName = target.textContent.trim(); 
            ModalManager.showRenameKBForm(kbId, oldName);
        },

        handleGlobalKeydown(e) {
            const targetTag = e.target.tagName;
            if (targetTag === 'INPUT' || targetTag === 'TEXTAREA' || e.target.isContentEditable) return;
            if (!ReviewEngine.currentNode) return;
            const keys = ConfigManager.getKeybinds();
            let actionButton = null;
            switch (e.key) {
                case keys.showAnswer: actionButton = document.querySelector('[data-action="show-answer"]'); break;
                case keys.know: actionButton = document.querySelector('[data-action="rate-kp"][data-status="know"]'); break;
                case keys.uncertain: actionButton = document.querySelector('[data-action="rate-kp"][data-status="uncertain"]'); break;
                case keys.dontKnow: actionButton = document.querySelector('[data-action="rate-kp"][data-status="dontKnow"]'); break;
                default: return; 
            }
            if (actionButton) {
                e.preventDefault(); 
                actionButton.click(); 
                actionButton.style.transform = 'scale(0.95)'; 
                setTimeout(() => { if (actionButton && document.body.contains(actionButton)) actionButton.style.transform = 'scale(1)'; }, 100);
            }
        },

        // --- 导入/导出处理器 ---
        async handleExportKB(kbId) {
            ModalManager.show('正在导出...', '<p>正在打包您的知识图谱（包括图片），请稍候...</p>', null);
            try {
                const kb = DataManager.getKnowledgeBase(kbId);
                const exportData = JSON.parse(JSON.stringify(kb)); 
                for (const node of exportData.nodes) {
                    if (node.imageId) {
                        const blob = await DBManager.getImage(node.imageId);
                        if (blob) node.imageData = await blobToBase64(blob);
                        delete node.imageId; 
                    }
                }
                const jsonString = JSON.stringify(exportData, null, 2);
                const blob = new Blob([jsonString], { type: 'application/json' });
                const url = URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                const safeName = exportData.name.replace(/[\/\\?%*:|"<>]/g, '_');
                a.download = `${safeName}_Graph_v2.json`; 
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

        async handleImportFile(event) {
            const file = event.target.files[0];
            if (!file) return;
            ModalManager.show('正在导入...', '<p>正在解析文件并导入图片...</p>', null);
            try {
                const fileContent = await file.text();
                const importData = JSON.parse(fileContent);
                await this.autoImportJSON(importData);
                ModalManager.hide();
                ModalManager.show('导入成功', `<p>知识库 "<strong>${UIRenderer.escapeHTML(importData.name || "导入的数据")}</strong>" 已成功导入。</p>`, '好的');
                this.router();
            } catch (e) {
                console.error('导入失败:', e);
                ModalManager.show('导入失败', `<p>发生错误: ${e.message}</p>`, '好的');
            } finally { event.target.value = null; }
        }
    };

    App.init();
});