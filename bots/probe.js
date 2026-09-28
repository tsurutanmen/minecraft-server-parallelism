// One bot: join, try the commands the load test will use, report what the server answered.
const mineflayer = require('mineflayer')
const [host, port, name] = ['127.0.0.1', 25565, process.argv[2] || 'probe0']
const bot = mineflayer.createBot({ host, port, username: name, version: '26.1', auth: 'offline' })
const log = (...a) => console.log(new Date().toISOString().slice(11, 19), ...a)
bot.on('messagestr', (m) => log('MSG', m))
bot.on('kicked', (r) => log('KICKED', JSON.stringify(r)))
bot.on('error', (e) => log('ERROR', e.message))
bot.once('spawn', async () => {
  log('SPAWN', bot.entity.position.toString())
  const wait = (ms) => new Promise((r) => setTimeout(r, ms))
  await wait(3000)
  bot.chat('/spreadplayers 768 768 0 8 false @s'); await wait(4000)
  log('POS after spreadplayers', bot.entity.position.toString())
  for (let i = 0; i < 5; i++) { bot.chat('/summon minecraft:villager ~2 ~ ~2'); await wait(250) }
  await wait(2000)
  bot.chat('/execute store result score @s x run summon minecraft:villager ~ ~ ~'); await wait(1000)
  log('entities near', Object.values(bot.entities).filter((e) => e.name === 'villager').length)
  bot.quit(); process.exit(0)
})
setTimeout(() => { log('TIMEOUT'); process.exit(1) }, 60000)
