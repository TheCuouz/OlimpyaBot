package info.desidia.olimpya.events;

import net.dv8tion.jda.api.JDA;
import net.dv8tion.jda.api.JDABuilder;
import net.dv8tion.jda.api.entities.channel.ChannelType;
import net.dv8tion.jda.api.events.message.MessageReceivedEvent;
import net.dv8tion.jda.api.hooks.ListenerAdapter;
import net.dv8tion.jda.api.requests.GatewayIntent;

public class MessageListener extends ListenerAdapter {
	public static void main(String[] args) {
		JDA jda = JDABuilder.createDefault("MTIwMjIzNDg5MzU0ODEyNjIxOQ.GO95jT.4-ojVTJ4wKHXTUJaqRooAq77vhN3U9vIug7njU")
				.enableIntents(GatewayIntent.MESSAGE_CONTENT) // enables explicit access to message.getContentDisplay()
				.build();
		//You can also add event listeners to the already built JDA instance
		// Note that some events may not be received if the listener is added after calling build()
		// This includes events such as the ReadyEvent
		jda.addEventListener(new MessageListener());
	}

	@Override
	public void onMessageReceived(MessageReceivedEvent event) {

		String messageSent = event.getMessage().getContentRaw();

		if (event.isFromType(ChannelType.PRIVATE)) {
			System.out.printf("[PM] %s: %s\n", event.getAuthor().getName(),
					event.getMessage().getContentDisplay());
		} else {
			System.out.printf("[%s][%s] %s: %s\n", event.getGuild().getName(),
					event.getChannel().getName(), event.getMember().getEffectiveName(),
					event.getMessage().getContentDisplay());
		}
		if(messageSent.equalsIgnoreCase("Desidia")){
			event.getChannel().sendMessage("Que pasa perro?").queue();

		}
	}
}