/* ポーカートレーニングラボ 共通ライブラリ（カード・レンジ・役判定） */
(function (global) {
  "use strict";
  var RANKS = "23456789TJQKA"; // index 0..12 (A=12)
  var SUITS = "shdc";
  var SUIT_SYM = { s: "♠", h: "♥", d: "♦", c: "♣" };
  var ORDER = "AKQJT98765432"; // 表示順（13x13表の行・列）

  // ---- カード ----
  // card id = rank*4 + suit
  function cardId(str) { return RANKS.indexOf(str[0]) * 4 + SUITS.indexOf(str[1]); }
  function cardStr(id) { return RANKS[id >> 2] + SUITS[id & 3]; }
  function cardHtml(id, cls) {
    if (id == null || id < 0) return '<span class="card empty ' + (cls || "") + '">?</span>';
    var r = RANKS[id >> 2], s = SUITS[id & 3];
    var red = s === "h" || s === "d";
    return '<span class="card ' + (red ? "red " : "") + (cls || "") + '">' + (r === "T" ? "10" : r) +
      '<span class="s">' + SUIT_SYM[s] + "</span></span>";
  }

  // ---- ハンドクラス（AKs, 72o, 99 など169種） ----
  function handClass(c1, c2) {
    var r1 = c1 >> 2, r2 = c2 >> 2;
    if (r1 < r2) { var t = r1; r1 = r2; r2 = t; }
    if (r1 === r2) return RANKS[r1] + RANKS[r2];
    return RANKS[r1] + RANKS[r2] + ((c1 & 3) === (c2 & 3) ? "s" : "o");
  }
  function gridClass(i, j) { // 行i 列j （0=A）
    var a = ORDER[i], b = ORDER[j];
    if (i === j) return a + b;
    return i < j ? a + b + "s" : b + a + "o";
  }
  function allClasses() {
    var out = [];
    for (var i = 0; i < 13; i++) for (var j = 0; j < 13; j++) out.push(gridClass(i, j));
    return out;
  }
  function combos(cls) { return cls.length === 2 ? 6 : cls[2] === "s" ? 4 : 12; }
  // クラスから具体的な2枚をランダムに作る
  function dealClass(cls) {
    var r1 = RANKS.indexOf(cls[0]), r2 = RANKS.indexOf(cls[1]);
    var s1 = Math.floor(Math.random() * 4), s2;
    if (cls.length === 2) { do { s2 = Math.floor(Math.random() * 4); } while (s2 === s1); }
    else if (cls[2] === "s") s2 = s1;
    else { do { s2 = Math.floor(Math.random() * 4); } while (s2 === s1); }
    return [r1 * 4 + s1, r2 * 4 + s2];
  }

  // ---- レンジ記法パーサ（"22+, A2s+, KTs+, AJo+, T9s" など） ----
  function parseRange(text) {
    var set = {};
    text.split(",").forEach(function (tok) {
      tok = tok.trim();
      if (!tok) return;
      var plus = tok.slice(-1) === "+";
      if (plus) tok = tok.slice(0, -1);
      var a = RANKS.indexOf(tok[0]), b = RANKS.indexOf(tok[1]), suf = tok[2] || "";
      if (a === b) { // ペア
        for (var r = a; r <= (plus ? 12 : a); r++) set[RANKS[r] + RANKS[r]] = true;
      } else {
        for (var k = b; k <= (plus ? a - 1 : b); k++) set[RANKS[a] + RANKS[k] + suf] = true;
      }
    });
    return set;
  }

  // ---- 6人テーブル・100BB・全員フォールドで回ってきたときのオープンレンジ（簡易版の目安） ----
  var RFI = {
    UTG: { name: "UTG（アンダー・ザ・ガン）", range: "55+, A2s+, KTs+, QTs+, JTs, T9s, 98s, AJo+, KQo",
      note: "最初に行動する最も不利なポジション。後ろに5人残っているので、強いハンドに絞ります。" },
    HJ: { name: "HJ（ハイジャック）", range: "33+, A2s+, K9s+, Q9s+, J9s+, T9s, 98s, 87s, ATo+, KJo+, QJo",
      note: "UTGの次。後ろが4人に減る分、スーテッドコネクターなどを少し足します。" },
    CO: { name: "CO（カットオフ）", range: "22+, A2s+, K7s+, Q8s+, J8s+, T8s+, 97s+, 87s, 76s, 65s, A9o+, KTo+, QTo+, JTo",
      note: "ボタンの1つ前。全ペアと多くのスーテッドハンドで参加できます。" },
    BTN: { name: "BTN（ボタン）", range: "22+, A2s+, K2s+, Q5s+, J7s+, T7s+, 96s+, 86s+, 75s+, 65s, 54s, A2o+, K9o+, Q9o+, J9o+, T9o, 98o",
      note: "フロップ以降に必ず最後に行動できる最も有利なポジション。最も広くオープンします。" },
    SB: { name: "SB（スモールブラインド）", range: "22+, A2s+, K4s+, Q7s+, J7s+, T7s+, 97s+, 86s+, 76s, 65s, 54s, A4o+, K9o+, Q9o+, J9o+, T9o",
      note: "BBとの1対1。フロップ以降は不利なポジションなので、BTNより少しだけ絞ります。" }
  };
  Object.keys(RFI).forEach(function (k) { RFI[k].set = parseRange(RFI[k].range); });
  function rangePct(set) {
    var n = 0; Object.keys(set).forEach(function (c) { n += combos(c); }); return n / 1326 * 100;
  }

  // ---- 7枚から役を評価（大きいほど強い） ----
  var CAT = ["ハイカード", "ワンペア", "ツーペア", "スリーカード", "ストレート", "フラッシュ", "フルハウス", "フォーカード", "ストレートフラッシュ"];
  function straightHigh(mask) {
    for (var hi = 12; hi >= 4; hi--) if (((mask >> (hi - 4)) & 31) === 31) return hi;
    if ((mask & 0x100F) === 0x100F) return 3; // A-2-3-4-5
    return -1;
  }
  function score(cat, ks) {
    var s = cat;
    for (var i = 0; i < 5; i++) s = s * 16 + (ks[i] != null ? ks[i] : 0);
    return s;
  }
  function evaluate(cards) {
    var cnt = new Array(13).fill(0), suitCnt = [0, 0, 0, 0], suitMask = [0, 0, 0, 0], mask = 0;
    for (var i = 0; i < cards.length; i++) {
      var r = cards[i] >> 2, s = cards[i] & 3;
      cnt[r]++; suitCnt[s]++; suitMask[s] |= 1 << r; mask |= 1 << r;
    }
    for (s = 0; s < 4; s++) if (suitCnt[s] >= 5) {
      var sf = straightHigh(suitMask[s]);
      if (sf >= 0) return score(8, [sf]);
      var fl = [];
      for (r = 12; r >= 0 && fl.length < 5; r--) if (suitMask[s] & (1 << r)) fl.push(r);
      var flushScore = score(5, fl);
    }
    var quads = -1, trips = [], pairs = [], singles = [];
    for (r = 12; r >= 0; r--) {
      if (cnt[r] === 4) quads = r;
      else if (cnt[r] === 3) trips.push(r);
      else if (cnt[r] === 2) pairs.push(r);
      else if (cnt[r] === 1) singles.push(r);
    }
    if (quads >= 0) {
      for (r = 12; r >= 0; r--) if (r !== quads && cnt[r]) break;
      return score(7, [quads, r]);
    }
    if (trips.length && (trips.length > 1 || pairs.length)) {
      var pr = trips.length > 1 ? Math.max(trips[1], pairs[0] != null ? pairs[0] : -1) : pairs[0];
      return score(6, [trips[0], pr]);
    }
    if (flushScore != null) return flushScore;
    var st = straightHigh(mask);
    if (st >= 0) return score(4, [st]);
    if (trips.length) return score(3, [trips[0]].concat(singles.slice(0, 2)));
    if (pairs.length >= 2) {
      var kick = singles.concat(pairs.slice(2)).sort(function (a, b) { return b - a; })[0];
      return score(2, [pairs[0], pairs[1], kick]);
    }
    if (pairs.length === 1) return score(1, [pairs[0]].concat(singles.slice(0, 3)));
    return score(0, singles.slice(0, 5));
  }
  function categoryName(sc) { return CAT[Math.floor(sc / 1048576)]; }

  // ---- 勝率計算（モンテカルロ／全列挙） ----
  // hands: [[c1,c2] or null(ランダム)], board: [ids] (0-5枚)
  function equity(hands, board, iterations) {
    var used = {};
    hands.forEach(function (h) { if (h) { used[h[0]] = used[h[1]] = 1; } });
    board.forEach(function (c) { used[c] = 1; });
    var deck = [];
    for (var c = 0; c < 52; c++) if (!used[c]) deck.push(c);
    var n = hands.length, win = new Array(n).fill(0), tie = new Array(n).fill(0), eq = new Array(n).fill(0);
    var need = 5 - board.length, randomPlayers = hands.filter(function (h) { return !h; }).length;
    var draw = need + randomPlayers * 2, total = 0;

    function run(extra) {
      var k = 0, b = board.slice(), hs = [];
      for (var p = 0; p < n; p++) hs.push(hands[p] || [extra[k++], extra[k++]]);
      while (b.length < 5) b.push(extra[k++]);
      var best = -1, scores = [];
      for (p = 0; p < n; p++) { var sc = evaluate(hs[p].concat(b)); scores.push(sc); if (sc > best) best = sc; }
      var winners = [];
      for (p = 0; p < n; p++) if (scores[p] === best) winners.push(p);
      winners.forEach(function (p) { if (winners.length === 1) win[p]++; else tie[p]++; eq[p] += 1 / winners.length; });
      total++;
    }
    if (randomPlayers === 0 && need <= 2) { // 全列挙（正確な値）
      if (need === 0) run([]);
      else if (need === 1) deck.forEach(function (x) { run([x]); });
      else for (var i = 0; i < deck.length; i++) for (var j = i + 1; j < deck.length; j++) run([deck[i], deck[j]]);
    } else {
      var arr = deck.slice();
      for (var it = 0; it < iterations; it++) {
        for (var d = 0; d < draw; d++) { // 部分シャッフル
          var r = d + Math.floor(Math.random() * (arr.length - d));
          var t = arr[d]; arr[d] = arr[r]; arr[r] = t;
        }
        run(arr);
      }
    }
    return { total: total, exact: randomPlayers === 0 && need <= 2,
      players: hands.map(function (_, p) { return { equity: eq[p] / total, win: win[p] / total, tie: tie[p] / total }; }) };
  }

  // ---- 13x13 レンジ表の描画 ----
  function rangeGridHtml(set, highlight) {
    var h = '<div class="rgrid">';
    for (var i = 0; i < 13; i++) for (var j = 0; j < 13; j++) {
      var c = gridClass(i, j);
      h += '<div class="' + (set[c] ? "in" : "") + (c === highlight ? " hl" : "") + '">' + c + "</div>";
    }
    return h + "</div>";
  }

  // ---- 保存（使えない環境でも動くように） ----
  function store(key, val) {
    try {
      if (val === undefined) return JSON.parse(localStorage.getItem(key) || "null");
      localStorage.setItem(key, JSON.stringify(val));
    } catch (e) { return null; }
  }

  global.Poker = { RANKS: RANKS, SUITS: SUITS, cardId: cardId, cardStr: cardStr, cardHtml: cardHtml,
    handClass: handClass, gridClass: gridClass, allClasses: allClasses, combos: combos, dealClass: dealClass,
    parseRange: parseRange, RFI: RFI, rangePct: rangePct, evaluate: evaluate, categoryName: categoryName,
    equity: equity, rangeGridHtml: rangeGridHtml, store: store };
})(window);
