<div id="wekoInputCredentials" class="modal fade">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">

            <div class="modal-header">
                <h3>${_("Connect a WEKO Account")}</h3>
            </div>

            <form>
                <div class="modal-body">

                    <div class="row">

                        <div class="col-sm-6">

                            <!-- Select WEKO installation -->
                            <div class="form-group">
                                <label for="hostSelect">${_("WEKO Repository")}</label>
                                <select class="form-control"
                                        id="hostSelect"
                                        data-bind="options: repositories,
                                                   optionsCaption: '${_("Select a WEKO repository")}',
                                                   value: selectedRepo,
                                                   event: { change: selectionChanged }">
                                </select>
                            </div>

                        </div>

                        <!-- for Basic Auth -->
                        <div class="col-sm-6" data-bind="visible: selectedRepo() == 'Other Repository (Basic Auth)'">
                            <div class="form-group">
                                <label for="wekoAddon">${_("WEKO SWORD URL")}</label>
                                <input class="form-control" data-bind="value: swordUrl" name="sword_url" ${'disabled' if disabled else ''} />
                            </div>
                            <div class="form-group">
                                <label for="wekoAddon">${_("WEKO Username")}</label>
                                <input class="form-control" data-bind="value: accessKey" name="access_key" ${'disabled' if disabled else ''} />
                            </div>
                            <div class="form-group">
                                <label for="wekoAddon">${_("WEKO Password")}</label>
                                <input type="password" class="form-control" data-bind="value: secretKey" name="secret_key" ${'disabled' if disabled else ''} />
                            </div>
                        </div>

                    </div><!-- end row -->

                    <!-- Flashed Messages -->
                    <div class="help-block">
                        <p data-bind="html: message, attr: {class: messageClass}"></p>
                    </div>

                </div><!-- end modal-body -->

                <div class="modal-footer">

                    <a href="#" class="btn btn-default" data-bind="click: clearModal" data-dismiss="modal">${_("Cancel")}</a>

                    <!-- Save Button -->
                    <button data-bind="click: connectOAuth" class="btn btn-success">${_("Connect")}</button>

                </div><!-- end modal-footer -->

            </form>

        </div><!-- end modal-content -->
    </div>
</div>
