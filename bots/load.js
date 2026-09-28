// Load generator: G groups of B bots, groups on a 4x4 grid 1920 blocks apart (Folia merges regions within 1536 blocks at default settings).
// The first bot of each group spawns villagers with /function bench:v50 (K times),
// then every bot wanders randomly until the end.
// usage: node load.js <groups> <botsPerGroup> <v50Times> <seconds>
const mineflayer = require('mineflayer')
const [G, B, K, SECS] = process.argv.slice(2).map(Number)
const wait = (ms) => new Promise((r) => setTimeout(r, ms))
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a)
const bots = []
let spawned = 0, kicked = 0

const SPACING = Number(process.env.SPACING || 1920)
function center(g) { return [((g % 4) - 1.5) * SPACING, (Math.floor(g / 4) - 1.5) * SPACING].map(Math.round) }

async function runBot(g, b) {
  const name = `g${g}b${b}`
  const bot = mineflayer.createBot({ host: '127.0.0.1', port: 25565, username: name, version: '26.1',
    auth: 'offline', viewDistance: 'short', physicsEnabled: true })
  bots.push(bot)
  bot.on('kicked', (r) => { kicked++; log('KICKED', name, JSON.stringify(r).slice(0, 200)) })
  bot.on('error', (e) => log('ERROR', name, e.message))
  await new Promise((r) => bot.once('spawn', r))
  spawned++
  const [x, z] = center(g)
  await wait(1000 + Math.random() * 2000)
  // /spreadplayers is a silent no-op on Folia, so teleport high up and fall (creative: no fall damage)
  const ox = Math.round((Math.random() - 0.5) * 16), oz = Math.round((Math.random() - 0.5) * 16)
  bot.chat('/gamemode creative @s'); await wait(500)
  bot.chat(`/tp @s ${x + ox} 200 ${z + oz}`)
  const t0 = Date.now()
  await wait(2000)
  while (Date.now() - t0 < 30000 && !(bot.entity && bot.entity.onGround && Math.abs(bot.entity.position.x - (x + ox)) < 4)) await wait(500)
  log('LANDED', name, bot.entity ? bot.entity.position.toString() : 'none', Date.now() - t0, 'ms')
  if (b === 0) {
    // Folia has no /function, so summon one by one (same 10x5 layout as the bench:v50 datapack function)
    for (let k = 0; k < K; k++) {
      for (let i = 0; i < 50; i++) { bot.chat(`/summon minecraft:villager ~${(i % 10) - 5} ~ ~${Math.floor(i / 10) - 2}`); await wait(40) }
    }
    log('SPAWNED_VILLAGERS', name, K * 50)
    // count what actually exists near the group (a silent no-op would show up here)
    await wait(3000)
    const reply = new Promise((r) => { const f = (m) => { const x = m.match(/Test passed\. Count: (\d+)/); if (x) { bot.off('messagestr', f); r(+x[1]) } }; bot.on('messagestr', f); setTimeout(() => r(-1), 5000) })
    bot.chat('/execute if entity @e[type=minecraft:villager,distance=..48]')
    log('VILLAGER_COUNT', name, await reply)
  }
  // wander: pick a random direction every 3 s, sometimes jump
  const iv = setInterval(() => {
    if (!bot.entity) return
    bot.look(Math.random() * Math.PI * 2, 0, true)
    bot.setControlState('forward', Math.random() < 0.8)
    bot.setControlState('jump', Math.random() < 0.3)
  }, 3000)
  bot.once('end', () => clearInterval(iv))
}

;(async () => {
  for (let g = 0; g < G; g++) for (let b = 0; b < B; b++) { runBot(g, b); await wait(250) }
  log('ALL_LAUNCHED')
  await wait(SECS * 1000)
  log('END spawned', spawned, 'kicked', kicked)
  for (const bot of bots) try { bot.quit() } catch {}
  await wait(2000); process.exit(0)
})()
