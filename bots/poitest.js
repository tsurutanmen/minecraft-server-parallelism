// Correctness test for "remember empty POI searches": villagers far from any POI must still take a
// workstation that appears later. Prints seconds from placing a composter to the first farmer.
const mineflayer = require('mineflayer')
const bot = mineflayer.createBot({ host: '127.0.0.1', port: 25565, username: 'poitest', version: '26.1', auth: 'offline' })
const w = (ms) => new Promise((r) => setTimeout(r, ms))
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a)
let last = ''
bot.on('messagestr', (m) => { last = m })
async function ask(cmd) { last = ''; bot.chat(cmd); await w(700); return last }
bot.once('spawn', async () => {
  await w(1500); bot.chat('/gamemode creative @s'); await w(400)
  bot.chat('/tp @s 3000 200 3000'); await w(8000)
  log('TIME', await ask('/time set day'))
  // flat, walkable floor so the workstation is reachable (a floating composter can never be taken)
  log('FLOOR', await ask('/fill ~-6 ~-1 ~-6 ~8 ~-1 ~8 minecraft:stone'))
  log('CLEAR', await ask('/fill ~-6 ~ ~-6 ~8 ~4 ~8 minecraft:air'))
  for (let i = 0; i < 5; i++) { bot.chat(`/summon minecraft:villager ~${i} ~ ~2`); await w(150) }
  log('SUMMONED', await ask('/execute if entity @e[type=minecraft:villager,distance=..16]'))
  log('BEFORE_JOBS', await ask('/execute if entity @e[type=minecraft:villager,distance=..16,nbt={VillagerData:{profession:"minecraft:none"}}]'))
  await w(90000) // long enough for several empty searches (every 20-40 ticks) to be remembered
  log('BOT_POS', bot.entity.position.toString(), 'onGround', bot.entity.onGround)
  log('VILLAGERS_NEAR64', await ask('/execute if entity @e[type=minecraft:villager,distance=..64]'))
  log('SETBLOCK', await ask('/setblock ~2 ~ ~4 minecraft:composter')); const t0 = Date.now()
  log('BLOCK_CHECK', await ask('/execute if block ~2 ~ ~4 minecraft:composter'))
  for (let i = 0; i < 36; i++) {
    await w(5000)
    const r = await ask('/execute if entity @e[type=minecraft:villager,distance=..64,nbt={VillagerData:{profession:"minecraft:farmer"}}]')
    if (/Count: [1-9]/.test(r)) { log('FARMER_AFTER_S', ((Date.now() - t0) / 1000).toFixed(0), r); process.exit(0) }
  }
  log('NO_FARMER_AFTER_S 180', last); process.exit(2)
})
setTimeout(() => { log('TIMEOUT'); process.exit(3) }, 400000)
